"""Log configuration with PII masking (NFR-P6).

Applied to the root logger and its handlers so emails/phones never reach the log
stream in the clear, regardless of which module emits them.
"""

from __future__ import annotations

import logging

from app.core.masking import mask_pii_text


class PiiMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        masked = mask_pii_text(message)
        if masked != message:
            record.msg = masked
            record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        logging.basicConfig(level=level)
    for handler in root.handlers:
        if not any(isinstance(f, PiiMaskingFilter) for f in handler.filters):
            handler.addFilter(PiiMaskingFilter())
    if not any(isinstance(f, PiiMaskingFilter) for f in root.filters):
        root.addFilter(PiiMaskingFilter())
