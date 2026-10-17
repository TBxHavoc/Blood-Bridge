"""P5: matching engine (pure, no DB)."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.matching.compatibility import is_compatible
from app.matching.engine import (
    DistanceLookup,
    MatchingSettings,
    RequestInput,
    SupplyUnit,
    detect_shortage,
    filter_eligible,
    match_request,
    order_requests,
    rank,
)

NOW = datetime(2026, 1, 1, 12, 0, 0)


def make_unit(
    code: str,
    group: str,
    bank_code: str = "BB_001",
    *,
    units_available: int = 5,
    units_reserved: int = 0,
    days_to_expiry: int = 5,
    hours_since_update: float = 0.5,
    component: str = "RBC",
    available: bool = True,
) -> SupplyUnit:
    return SupplyUnit(
        inventory_id=f"inv-{code}",
        inventory_code=code,
        blood_bank_id=f"bank-{bank_code}",
        blood_bank_code=bank_code,
        blood_bank_name=f"Bank {bank_code}",
        blood_group=group,
        component_type=component,
        units_available=units_available,
        units_reserved=units_reserved,
        expiry_date=(NOW + timedelta(days=days_to_expiry)).date(),
        is_available=available,
        last_updated=NOW - timedelta(hours=hours_since_update),
    )


def make_request(
    group: str = "O-",
    *,
    quantity: int = 1,
    urgency: int = 3,
    component: str = "RBC",
    ts: datetime | None = None,
    req_id: str = "req-1",
) -> RequestInput:
    return RequestInput(
        request_id=req_id,
        request_code=f"REQ_{req_id}",
        hospital_id="hosp-1",
        hospital_code="H_001",
        blood_group=group,
        component_type=component,
        quantity_units=quantity,
        urgency=urgency,
        request_timestamp=ts or NOW,
    )


def lookup(**eta_by_bank: int) -> DistanceLookup:
    distances = {( "H_001", bank): (eta / 60.0 * 40.0, eta) for bank, eta in eta_by_bank.items()}
    return DistanceLookup(distances)


# --- compatibility ---------------------------------------------------------


def test_compatibility_matrix() -> None:
    assert is_compatible("O-", "O-")
    assert not is_compatible("O-", "O+")
    assert is_compatible("AB+", "B-")
    assert not is_compatible("A+", "B+")


# --- eligibility -----------------------------------------------------------


def test_eligibility_filters() -> None:
    request = make_request("O-", quantity=2)
    units = [
        make_unit("INV_OK", "O-"),
        make_unit("INV_INCOMPATIBLE", "O+"),
        make_unit("INV_INSUFFICIENT", "O-", units_available=1),
        make_unit("INV_RESERVED", "O-", units_available=3, units_reserved=3),
        make_unit("INV_EXPIRED", "O-", days_to_expiry=-1),
        make_unit("INV_UNAVAILABLE", "O-", available=False),
        make_unit("INV_WRONG_COMPONENT", "O-", component="WHOLE_BLOOD"),
    ]
    eligible = filter_eligible(request, units, lookup(BB_001=10), NOW)
    assert [u.inventory_code for u in eligible] == ["INV_OK"]


def test_expiring_before_arrival_is_excluded() -> None:
    request = make_request("O-")
    unit = make_unit("INV_SOON", "O-", days_to_expiry=0)  # expires today
    # ETA of 3000 min -> arrival is days away, unit cannot survive the trip.
    eligible = filter_eligible(request, [unit], lookup(BB_001=3000), NOW)
    assert eligible == []


# --- scoring ---------------------------------------------------------------


def test_compute_score_full_marks() -> None:
    request = make_request("O-")
    unit = make_unit("INV_FAST", "O-", days_to_expiry=1, hours_since_update=0.2)
    settings = MatchingSettings()
    ranked = rank(request, [unit], lookup(BB_001=0), settings, NOW)
    top = ranked[0]
    assert top.match_score == 100.0
    assert top.breakdown == {"eta": 50.0, "expiry": 30.0, "freshness": 20.0}


def test_explanation_matches_breakdown() -> None:
    request = make_request("O-", urgency=5)
    unit = make_unit("INV_EXPL", "O-", days_to_expiry=4, hours_since_update=3)
    settings = MatchingSettings()
    top = rank(request, [unit], lookup(BB_001=30), settings, NOW)[0]
    assert f"{top.match_score:.2f}/100" in top.explanation
    assert round(sum(top.breakdown.values()), 2) == top.match_score


def test_eta_beyond_max_scores_zero_for_eta() -> None:
    request = make_request("O-")
    unit = make_unit("INV_FAR", "O-")
    settings = MatchingSettings(max_eta_minutes=180)
    top = rank(request, [unit], lookup(BB_001=500), settings, NOW)[0]
    assert top.breakdown["eta"] == 0.0


# --- ranking ---------------------------------------------------------------


def test_ranking_prefers_lower_eta() -> None:
    request = make_request("O-")
    units = [
        make_unit("INV_SLOW", "O-", bank_code="BB_002"),
        make_unit("INV_FAST", "O-", bank_code="BB_003"),
    ]
    ranked = rank(request, units, lookup(BB_002=120, BB_003=10), MatchingSettings(), NOW)
    assert [c.inventory.inventory_code for c in ranked] == ["INV_FAST", "INV_SLOW"]
    assert [c.ranking for c in ranked] == [1, 2]


# --- request priority ------------------------------------------------------


def test_request_priority_urgency_then_time() -> None:
    low = make_request(urgency=1, ts=NOW - timedelta(hours=1), req_id="low")
    high_new = make_request(urgency=5, ts=NOW, req_id="high-new")
    high_old = make_request(urgency=5, ts=NOW - timedelta(minutes=10), req_id="high-old")
    ordered = order_requests([low, high_new, high_old])
    assert [r.request_id for r in ordered] == ["high-old", "high-new", "low"]


# --- shortage --------------------------------------------------------------


def test_shortage_no_eligible_is_complete() -> None:
    request = make_request("O-")
    outcome = match_request(request, [], lookup(), MatchingSettings(), NOW)
    assert outcome.shortage_type == "COMPLETE"
    assert outcome.matches == []


def test_shortage_low_score_is_partial() -> None:
    request = make_request("O-")
    unit = make_unit("INV_MEH", "O-", days_to_expiry=100, hours_since_update=100)
    ranked = rank(request, [unit], lookup(BB_001=175), MatchingSettings(), NOW)
    assert detect_shortage([unit], ranked, MatchingSettings()) == "PARTIAL"


def test_match_request_end_to_end() -> None:
    request = make_request("AB+", quantity=2)
    units = [
        make_unit("INV_A", "A-", bank_code="BB_001"),
        make_unit("INV_O", "O-", bank_code="BB_002"),
    ]
    outcome = match_request(request, units, lookup(BB_001=20, BB_002=60), MatchingSettings(), NOW)
    assert outcome.shortage_type is None
    assert outcome.eligible_count == 2
    assert outcome.matches[0].ranking == 1
