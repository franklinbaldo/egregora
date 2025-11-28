"""Privacy utilities to guard against personal data leaks.

TODO: This module contains regex-based PII detection (validate_text_privacy) that is
currently UNUSED in the pipeline. The system uses a layered approach instead:
1. Structural anonymization (privacy/anonymizer.py) - runs BEFORE LLMs
2. LLM-native prevention (prompt templates) - instructs LLMs to avoid PII
3. Post-generation detection (agents/enricher.py) - checks for PII_DETECTED marker

Consider either:
- Integrating validate_text_privacy() into post-generation validation
- Removing this module if regex-based detection is not needed
- Documenting this as a fallback/defense-in-depth mechanism
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from egregora.privacy.patterns import PII_PATTERNS, UUID_PATTERN

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class PrivacyViolationError(RuntimeError):
    """Raised when generated content exposes sensitive data."""


def _within_any(span: tuple[int, int], ranges: Sequence[tuple[int, int]]) -> bool:
    """Return ``True`` if ``span`` is fully contained inside one of ``ranges``."""
    start, end = span
    return any((r_start <= start and end <= r_end for r_start, r_end in ranges))


def validate_text_privacy(
    text: str,
    *,
    action: Literal["warn", "redact", "skip"] = "warn",
    enabled: bool = True,
) -> tuple[str, bool]:
    """Ensure text does not contain PII patterns (phone numbers, emails, etc.).

    Args:
        text: Text content to validate for privacy violations
        action: Action to take on PII detection ("warn", "redact", "skip")
        enabled: If False, skip PII detection entirely

    Returns:
        Tuple of (text, is_valid):
            - text: Original or redacted text depending on action
            - is_valid: True if no PII detected or action handled it

    Raises:
        PrivacyViolationError: If action="skip" and PII is detected

    """
    # If detection is disabled, return text as-is
    if not enabled:
        return (text, True)

    uuid_spans = [(match.start(), match.end()) for match in UUID_PATTERN.finditer(text)]
    pii_detected = False
    redacted_text = text

    for pattern in PII_PATTERNS:
        for match in pattern.regex.finditer(text):
            span = match.span()
            if _within_any(span, uuid_spans):
                continue

            pii_detected = True
            msg = f"Possible PII leak detected: {pattern.description}"

            if action == "warn":
                logger.warning(msg)
            elif action == "redact":
                # Replace PII with [REDACTED]
                start, end = span
                redacted_text = redacted_text[:start] + "[REDACTED]" + redacted_text[end:]
                logger.warning(f"{msg} - Redacted in output")
            elif action == "skip":
                raise PrivacyViolationError(msg)

    return (redacted_text, not pii_detected)


__all__ = ["PrivacyViolationError", "validate_text_privacy"]
