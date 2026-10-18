"""Synthetic data generation.

All data is fabricated and marked SIMULATED FOR DEMONSTRATION PURPOSES. It
mimics the eRaktKosh structure (blood banks, hospitals, inventory, requests,
distances) but contains no real patient, donor or organisational data.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta

# Weighted blood-group distribution (approximate real-world frequencies).
BLOOD_GROUP_WEIGHTS: dict[str, float] = {
    "O+": 0.35,
    "A+": 0.25,
    "B+": 0.15,
    "AB+": 0.05,
    "O-": 0.07,
    "A-": 0.05,
    "B-": 0.05,
    "AB-": 0.03,
}

CITIES: list[tuple[str, float, float]] = [
    ("Mumbai", 19.0760, 72.8777),
    ("Delhi", 28.6139, 77.2090),
    ("Bengaluru", 12.9716, 77.5946),
    ("Chennai", 13.0827, 80.2707),
    ("Pune", 18.5204, 73.8567),
    ("Hyderabad", 17.3850, 78.4867),
    ("Kolkata", 22.5726, 88.3639),
    ("Ahmedabad", 23.0225, 72.5714),
    ("Jaipur", 26.9124, 75.7873),
    ("Lucknow", 26.8467, 80.9462),
    ("Surat", 21.1702, 72.8311),
    ("Nagpur", 21.1458, 79.0882),
    ("Indore", 22.7196, 75.8577),
    ("Kochi", 9.9312, 76.2673),
]

# Shelf life in days by component (whole blood ~35, red cells ~42).
SHELF_LIFE_DAYS: dict[str, int] = {"WHOLE_BLOOD": 35, "RBC": 42}


def _jitter(value: float, spread: float = 0.05) -> float:
    return round(value + random.uniform(-spread, spread), 6)


def pick_blood_group() -> str:
    return random.choices(
        list(BLOOD_GROUP_WEIGHTS.keys()),
        weights=list(BLOOD_GROUP_WEIGHTS.values()),
        k=1,
    )[0]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return round(2 * radius * math.asin(math.sqrt(a)), 2)


def generate_blood_banks(n: int = 20) -> list[dict]:
    banks = []
    for i in range(n):
        city, lat, lon = CITIES[i % len(CITIES)]
        banks.append(
            {
                "code": f"BB_{i + 1:03d}",
                "name": f"{city} Blood Bank {i + 1}",
                "city": city,
                "latitude": _jitter(lat),
                "longitude": _jitter(lon),
                "phone": f"+91-{random.randint(20, 99)}-{random.randint(1000000, 9999999)}",
                "capacity_units": random.randint(200, 1200),
                "is_active": True,
            }
        )
    return banks


def generate_hospitals(n: int = 10) -> list[dict]:
    hospitals = []
    for i in range(n):
        city, lat, lon = CITIES[i % len(CITIES)]
        hospitals.append(
            {
                "code": f"H_{i + 1:03d}",
                "name": f"{city} General Hospital {i + 1}",
                "city": city,
                "latitude": _jitter(lat),
                "longitude": _jitter(lon),
                "phone": f"+91-{random.randint(20, 99)}-{random.randint(1000000, 9999999)}",
                "emergency_dept_capacity": random.choice(["small", "medium", "large"]),
                "is_active": True,
            }
        )
    return hospitals


def generate_inventory(
    banks: list[dict], min_per_bank: int = 5, max_per_bank: int = 8, today: date | None = None
) -> list[dict]:
    today = today or date.today()
    inventory: list[dict] = []
    counter = 0
    for bank in banks:
        for _ in range(random.randint(min_per_bank, max_per_bank)):
            counter += 1
            component = "RBC" if random.random() < 0.7 else "WHOLE_BLOOD"
            shelf_life = SHELF_LIFE_DAYS[component]
            # collection within the last (shelf_life - 1) days so expiry spans a range.
            days_ago = random.randint(1, shelf_life - 1)
            collection = today - timedelta(days=days_ago)
            expiry = collection + timedelta(days=shelf_life)
            units_available = random.randint(3, 30)
            # Occasionally hold some units (already reserved).
            units_reserved = random.choice([0, 0, 0, 1, 2]) if units_available > 4 else 0
            inventory.append(
                {
                    "code": f"INV_{counter:03d}",
                    "blood_bank_code": bank["code"],
                    "blood_group": pick_blood_group(),
                    "component_type": component,
                    "units_available": units_available,
                    "units_reserved": units_reserved,
                    "collection_date": collection,
                    "expiry_date": expiry,
                    "storage_location_code": f"RACK_{random.choice('ABC')}{random.randint(1, 9)}",
                    "is_available": True,
                }
            )
    return inventory


def generate_requests(
    hospitals: list[dict], n: int = 40, now: datetime | None = None
) -> list[dict]:
    now = now or datetime.utcnow()
    requests: list[dict] = []
    for i in range(n):
        hospital = random.choice(hospitals)
        submitted = now - timedelta(minutes=random.randint(1, 2880))
        required_by = submitted + timedelta(minutes=random.choice([30, 60, 120, 240, 480]))
        status = random.choices(
            ["OPEN", "FULFILLED", "CANCELLED", "EXPIRED"], weights=[0.6, 0.2, 0.1, 0.1], k=1
        )[0]
        requests.append(
            {
                "code": f"REQ_SEED_{i + 1:03d}",
                "hospital_code": hospital["code"],
                "blood_group": pick_blood_group(),
                "component_type": "RBC" if random.random() < 0.7 else "WHOLE_BLOOD",
                "quantity_units": random.randint(1, 6),
                "urgency": random.randint(1, 5),
                "required_by_timestamp": required_by,
                "request_timestamp": submitted,
                "status": status,
            }
        )
    return requests


def generate_distances(
    hospitals: list[dict], banks: list[dict], speed_kmph: int = 60
) -> list[dict]:
    distances: list[dict] = []
    for hospital in hospitals:
        for bank in banks:
            km = haversine_km(
                hospital["latitude"],
                hospital["longitude"],
                bank["latitude"],
                bank["longitude"],
            )
            eta = max(1, round(km / speed_kmph * 60))
            distances.append(
                {
                    "origin_id": hospital["code"],
                    "destination_id": bank["code"],
                    "origin_type": "hospital",
                    "destination_type": "blood_bank",
                    "distance_km": km,
                    "eta_minutes": eta,
                }
            )
    return distances
