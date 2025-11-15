"""Privacy utilities to guard against personal data leaks."""

from __future__ import annotations
from typing import TYPE_CHECKING
from egregora.privacy.patterns import PII_PATTERNS, UUID_PATTERN

if TYPE_CHECKING:
    from collections.abc import Sequence


class PrivacyViolationError(RuntimeError):
    """Raised when generated content exposes sensitive data."""


def _within_any(span: tuple[int, int], ranges: Sequence[tuple[int, int]]) -> bool:
    """Return ``True`` if ``span`` is fully contained inside one of ``ranges``."""
    start, end = span
    return any((r_start <= start and end <= r_end for r_start, r_end in ranges))


def validate_text_privacy(text: str) -> bool:
    """Ensure text does not contain PII patterns (phone numbers, emails, etc.).

    Args:
        text: Text content to validate for privacy violations

    Returns:
        True if no PII detected

    Raises:
        PrivacyViolationError: If PII patterns are found outside UUID contexts

    """
    uuid_spans = [(match.start(), match.end()) for match in UUID_PATTERN.finditer(text)]
    for pattern in PII_PATTERNS:
        for match in pattern.regex.finditer(text):
            span = match.span()
            if _within_any(span, uuid_spans):
                continue
            msg = f"Possible PII leak detected: {pattern.description}"
            raise PrivacyViolationError(msg)
    return True


__all__ = ["PrivacyViolationError", "validate_text_privacy"]
