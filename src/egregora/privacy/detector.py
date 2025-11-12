"""Privacy utilities to guard against personal data leaks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class PrivacyViolationError(RuntimeError):
    """Raised when generated content exposes sensitive data."""


@dataclass(frozen=True)
class _PrivacyPattern:
    description: str
    regex: re.Pattern[str]


_PHONE_PATTERNS: tuple[_PrivacyPattern, ...] = (
    _PrivacyPattern(
        description="international phone number", regex=re.compile("\\+\\d{2}\\s?\\d{2}\\s?\\d{4,5}-?\\d{4}")
    ),
    _PrivacyPattern(description="local phone number with hyphen", regex=re.compile("\\b\\d{3,5}-\\d{4}\\b")),
    _PrivacyPattern(
        description="parenthesized local phone number",
        regex=re.compile("\\(\\s*\\d{2,3}\\s*\\)\\s*\\d{3,5}-\\d{4}"),
    ),
)
_EMAIL_PATTERN = _PrivacyPattern(
    description="email address",
    regex=re.compile("[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", re.IGNORECASE),
)
_BRAZILIAN_ID_PATTERNS: tuple[_PrivacyPattern, ...] = (
    _PrivacyPattern(description="CPF identifier", regex=re.compile("\\b\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2}\\b")),
    _PrivacyPattern(
        description="CNPJ identifier", regex=re.compile("\\b\\d{2}\\.\\d{3}\\.\\d{3}/\\d{4}-\\d{2}\\b")
    ),
)
_PII_PATTERNS: tuple[_PrivacyPattern, ...] = (*_PHONE_PATTERNS, _EMAIL_PATTERN, *_BRAZILIAN_ID_PATTERNS)
_UUID_PATTERN = re.compile("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


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
    uuid_spans = [(match.start(), match.end()) for match in _UUID_PATTERN.finditer(text)]
    for pattern in _PII_PATTERNS:
        for match in pattern.regex.finditer(text):
            span = match.span()
            if _within_any(span, uuid_spans):
                continue
            msg = f"Possible PII leak detected: {pattern.description}"
            raise PrivacyViolationError(msg)
    return True


# Legacy alias for backward compatibility (deprecated)
validate_newsletter_privacy = validate_text_privacy


__all__ = ["PrivacyViolationError", "validate_newsletter_privacy", "validate_text_privacy"]
