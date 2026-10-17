"""Blood-group compatibility (red cells / whole blood only).

recipient -> set of compatible donor groups. Validated for red cells only
(PRD section 7 caveat: plasma compatibility is reversed and out of scope).
"""

from __future__ import annotations

COMPATIBILITY: dict[str, set[str]] = {
    "O+": {"O+", "O-"},
    "O-": {"O-"},
    "A+": {"A+", "A-", "O+", "O-"},
    "A-": {"A-", "O-"},
    "B+": {"B+", "B-", "O+", "O-"},
    "B-": {"B-", "O-"},
    "AB+": {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"},
    "AB-": {"AB-", "A-", "B-", "O-"},
}


def is_compatible(recipient_group: str, donor_group: str) -> bool:
    """True when a unit of `donor_group` can be given to a `recipient_group`."""
    return donor_group in COMPATIBILITY.get(recipient_group, set())
