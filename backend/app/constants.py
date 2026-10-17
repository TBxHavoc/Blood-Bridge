"""Domain constants and allowed-value sets.

These are the single source of truth for validated enums. They are used both for
CHECK constraints (so values are DB-enforced and Db2-portable — no inline ENUM)
and for API validation.
"""

from __future__ import annotations

BLOOD_GROUPS: tuple[str, ...] = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")

# MVP is scoped to red cells only (PRD section 7 caveat: plasma compatibility is
# reversed, so plasma is intentionally out of scope).
COMPONENT_TYPES: tuple[str, ...] = ("WHOLE_BLOOD", "RBC")

ROLES: tuple[str, ...] = ("hospital_user", "bloodbank_user", "admin", "auditor")

# Six-state request lifecycle (PRD section 8.4). Supersedes the SRS status list.
REQUEST_STATUSES: tuple[str, ...] = (
    "OPEN",
    "HELD",
    "CONFIRMED",
    "CANCELLED",
    "EXPIRED",
    "FULFILLED",
)

RESERVATION_STATUSES: tuple[str, ...] = ("ACTIVE", "CONFIRMED", "RELEASED", "EXPIRED")

ALERT_TYPES: tuple[str, ...] = (
    "MATCH_FOUND",
    "SHORTAGE_DETECTED",
    "MATCH_EXPIRED",
    "ALLOCATED",
)

SHORTAGE_TYPES: tuple[str, ...] = ("COMPLETE", "PARTIAL")

URGENCY_LABELS: dict[int, str] = {
    1: "Routine",
    2: "Moderately urgent",
    3: "Urgent",
    4: "Critical",
    5: "Life-threatening",
}

# Matching algorithm version stamped on every result (FR-13).
ALGORITHM_VERSION = "1.0"
