"""PII masking (NFR-P6): mask emails and phone numbers in logs and auditor views.

Blood Bridge never stores patient or donor identity, but user contact details
(email/phone) are still PII. The auditor view and the log stream must show them
masked.
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(\+?[0-9][0-9\-\s().]{6,}[0-9])(?!\d)")

_MASK = "***"


def mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    if not domain:
        return _MASK
    head = local[:1] if local else ""
    return f"{head}{_MASK}@{domain}"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) <= 3:
        return _MASK
    return f"{_MASK}{digits[-3:]}"


def _mask_phone_match(match: re.Match) -> str:
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    # Only treat as a phone if it has >= 10 digits or an explicit country code.
    if len(digits) < 10 and not raw.strip().startswith("+"):
        return raw
    return mask_phone(raw)


def mask_pii_text(text: str | None) -> str | None:
    """Mask any emails and phone numbers found in a free-text blob."""
    if not text:
        return text
    text = _EMAIL_RE.sub(lambda m: mask_email(m.group(0)), text)
    return _PHONE_RE.sub(_mask_phone_match, text)
