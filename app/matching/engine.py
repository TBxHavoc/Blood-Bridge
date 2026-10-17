"""Matching engine: eligibility, request priority, supply ranking, shortage.

Pure Python, no DB access — the API layer loads rows, adapts them to the small
dataclasses here, and passes a distance lookup. This keeps the engine trivially
unit-testable and independent of the storage layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.matching.compatibility import is_compatible

# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


@dataclass
class RequestInput:
    request_id: str
    request_code: str
    hospital_id: str
    hospital_code: str
    blood_group: str
    component_type: str
    quantity_units: int
    urgency: int
    request_timestamp: datetime
    required_by_timestamp: datetime | None = None


@dataclass
class SupplyUnit:
    inventory_id: str
    inventory_code: str
    blood_bank_id: str
    blood_bank_code: str
    blood_bank_name: str
    blood_group: str
    component_type: str
    units_available: int
    units_reserved: int
    expiry_date: date
    is_available: bool
    last_updated: datetime

    @property
    def usable_units(self) -> int:
        return self.units_available - self.units_reserved


@dataclass
class MatchCandidate:
    inventory: SupplyUnit
    ranking: int
    match_score: float
    distance_km: float
    eta_minutes: int
    explanation: str
    breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class MatchOutcome:
    request_id: str
    matches: list[MatchCandidate]
    shortage_type: str | None  # None | "COMPLETE" | "PARTIAL"
    eligible_count: int


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


@dataclass
class MatchingSettings:
    weight_eta: float = 50
    weight_expiry: float = 30
    weight_freshness: float = 20
    max_eta_minutes: float = 180
    score_threshold: float = 50
    eta_speed_kmph: float = 60
    expiry_bands: list[dict] = field(
        default_factory=lambda: [
            {"max_days": 3, "points": 30},
            {"max_days": 7, "points": 25},
            {"max_days": 30, "points": 15},
            {"max_days": None, "points": 5},
        ]
    )
    freshness_bands: list[dict] = field(
        default_factory=lambda: [
            {"max_hours": 1, "points": 20},
            {"max_hours": 6, "points": 10},
            {"max_hours": 24, "points": 5},
            {"max_hours": None, "points": 0},
        ]
    )
    algorithm_version: str = "1.0"

    as_dict: dict = field(default_factory=dict, init=False)

    def weights_snapshot(self) -> dict:
        return {
            "weight_eta": self.weight_eta,
            "weight_expiry": self.weight_expiry,
            "weight_freshness": self.weight_freshness,
            "max_eta_minutes": self.max_eta_minutes,
            "score_threshold": self.score_threshold,
            "expiry_bands": self.expiry_bands,
            "freshness_bands": self.freshness_bands,
            "algorithm_version": self.algorithm_version,
        }


# --------------------------------------------------------------------------- #
# Distances
# --------------------------------------------------------------------------- #


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


class DistanceLookup:
    """Precomputed (hospital_code, bank_code) -> (km, eta), with Haversine fallback."""

    def __init__(
        self,
        distances: dict[tuple[str, str], tuple[float, int]],
        coords: dict[str, tuple[float, float]] | None = None,
        speed_kmph: float = 60,
    ) -> None:
        self._distances = distances
        self._coords = coords or {}
        self._speed = speed_kmph

    def get(self, hospital_code: str, bank_code: str) -> tuple[float, int]:
        key = (hospital_code, bank_code)
        if key in self._distances:
            return self._distances[key]
        if hospital_code in self._coords and bank_code in self._coords:
            hlat, hlon = self._coords[hospital_code]
            blat, blon = self._coords[bank_code]
            km = haversine_km(hlat, hlon, blat, blon)
            return km, max(1, round(km / self._speed * 60))
        # Unknown pair: treat as very far so it ranks last but is still returned.
        return 9999.0, 9999


# --------------------------------------------------------------------------- #
# Phase 1: eligibility
# --------------------------------------------------------------------------- #


def filter_eligible(
    request: RequestInput,
    units: list[SupplyUnit],
    lookup: DistanceLookup,
    now: datetime,
) -> list[SupplyUnit]:
    """Deterministic filter — never scores (PRD section 7, Phase 1)."""
    today = now.date()
    eligible: list[SupplyUnit] = []
    for unit in units:
        if not unit.is_available:
            continue
        if not is_compatible(request.blood_group, unit.blood_group):
            continue
        if request.component_type and unit.component_type != request.component_type:
            continue
        if unit.usable_units < request.quantity_units:
            continue
        if unit.expiry_date < today:
            continue  # already expired
        _, eta_minutes = lookup.get(request.hospital_code, unit.blood_bank_code)
        arrival = (now + timedelta(minutes=eta_minutes)).date()
        if unit.expiry_date < arrival:
            continue  # would expire before it could arrive
        eligible.append(unit)
    return eligible


# --------------------------------------------------------------------------- #
# Phase 2: request priority (across competing requests)
# --------------------------------------------------------------------------- #


def request_priority_key(request: RequestInput) -> tuple:
    """Higher urgency first, then earlier request, then id (FR-31, fairness)."""
    return (-request.urgency, request.request_timestamp, request.request_id)


def order_requests(requests: list[RequestInput]) -> list[RequestInput]:
    return sorted(requests, key=request_priority_key)


# --------------------------------------------------------------------------- #
# Phase 3: supply ranking (per request)
# --------------------------------------------------------------------------- #


def _band_points(value: float, bands: list[dict], bound_key: str) -> float:
    for band in bands:
        bound = band.get(bound_key)
        if bound is None or value <= bound:
            return float(band["points"])
    return float(bands[-1]["points"])


def compute_score(
    request: RequestInput,
    unit: SupplyUnit,
    eta_minutes: int,
    settings: MatchingSettings,
    now: datetime,
) -> tuple[float, dict[str, float]]:
    """Score a single unit 0–100 and return the score plus its breakdown.

    The breakdown is the single source of truth: the explanation is rendered
    from it, so what the user reads always matches the calculation (FR-13).
    """
    # ETA (default max 50 points): 0 at or beyond max_eta.
    if eta_minutes >= settings.max_eta_minutes:
        eta_points = 0.0
    else:
        eta_points = (1 - eta_minutes / settings.max_eta_minutes) * settings.weight_eta

    # Expiry suitability (first-expiring-first-out).
    days_until_expiry = (unit.expiry_date - now.date()).days
    expiry_points = _band_points(days_until_expiry, settings.expiry_bands, "max_days")

    # Data freshness (hours since the inventory row was updated).
    hours_since_update = max(0.0, (now - unit.last_updated).total_seconds() / 3600)
    freshness_points = _band_points(hours_since_update, settings.freshness_bands, "max_hours")

    breakdown = {
        "eta": round(eta_points, 2),
        "expiry": round(expiry_points, 2),
        "freshness": round(freshness_points, 2),
    }
    total = round(sum(breakdown.values()), 2)
    return total, breakdown


def build_explanation(
    request: RequestInput,
    unit: SupplyUnit,
    breakdown: dict[str, float],
    score: float,
    distance_km: float,
    eta_minutes: int,
    settings: MatchingSettings,
    now: datetime,
) -> str:
    """Render a human-readable explanation from the score breakdown."""
    days_until_expiry = (unit.expiry_date - now.date()).days
    hours_since_update = max(0.0, (now - unit.last_updated).total_seconds() / 3600)
    total_weight = settings.weight_eta + settings.weight_expiry + settings.weight_freshness
    return (
        f"ETA {eta_minutes} min ({distance_km:.1f} km) "
        f"[{breakdown['eta']:.2f}/{settings.weight_eta:g}]; "
        f"expires in {days_until_expiry} d "
        f"[{breakdown['expiry']:.2f}/{settings.weight_expiry:g}]; "
        f"inventory fresh {hours_since_update:.1f} h ago "
        f"[{breakdown['freshness']:.2f}/{settings.weight_freshness:g}] "
        f"= {score:.2f}/{total_weight:g}"
    )


def rank(
    request: RequestInput,
    units: list[SupplyUnit],
    lookup: DistanceLookup,
    settings: MatchingSettings,
    now: datetime,
) -> list[MatchCandidate]:
    candidates: list[MatchCandidate] = []
    for unit in units:
        distance_km, eta_minutes = lookup.get(request.hospital_code, unit.blood_bank_code)
        score, breakdown = compute_score(request, unit, eta_minutes, settings, now)
        explanation = build_explanation(
            request, unit, breakdown, score, distance_km, eta_minutes, settings, now
        )
        candidates.append(
            MatchCandidate(
                inventory=unit,
                ranking=0,
                match_score=score,
                distance_km=round(distance_km, 2),
                eta_minutes=eta_minutes,
                explanation=explanation,
                breakdown=breakdown,
            )
        )

    # Highest score first; ties broken by lower ETA then inventory code (stable).
    candidates.sort(key=lambda c: (-c.match_score, c.eta_minutes, c.inventory.inventory_code))
    for index, candidate in enumerate(candidates, start=1):
        candidate.ranking = index
    return candidates


# --------------------------------------------------------------------------- #
# Phase 4: shortage
# --------------------------------------------------------------------------- #


def detect_shortage(
    eligible: list[SupplyUnit],
    ranked: list[MatchCandidate],
    settings: MatchingSettings,
) -> str | None:
    if not eligible:
        return "COMPLETE"
    if ranked and ranked[0].match_score < settings.score_threshold:
        return "PARTIAL"
    return None


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def match_request(
    request: RequestInput,
    units: list[SupplyUnit],
    lookup: DistanceLookup,
    settings: MatchingSettings,
    now: datetime,
) -> MatchOutcome:
    eligible = filter_eligible(request, units, lookup, now)
    ranked = rank(request, eligible, lookup, settings, now) if eligible else []
    shortage = detect_shortage(eligible, ranked, settings)
    return MatchOutcome(
        request_id=request.request_id,
        matches=ranked,
        shortage_type=shortage,
        eligible_count=len(eligible),
    )
