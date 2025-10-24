"""Privacy utilities to guard against personal data leaks."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass


class PrivacyViolationError(RuntimeError):
    """Raised when generated content exposes sensitive data."""


@dataclass(frozen=True)
class _PrivacyPattern:
    description: str
    regex: re.Pattern[str]


# Patterns that indicate potential phone number leaks. The expressions are kept
# deliberately conservative; if a pattern matches we prefer to fail fast and
# surface an explicit error to the caller.
_PHONE_PATTERNS: tuple[_PrivacyPattern, ...] = (
    _PrivacyPattern(
        description="international phone number",
        regex=re.compile(r"\+\d{2}\s?\d{2}\s?\d{4,5}-?\d{4}"),
    ),
    _PrivacyPattern(
        description="local phone number with hyphen",
        regex=re.compile(r"\b\d{3,5}-\d{4}\b"),
    ),
    _PrivacyPattern(
        description="parenthesized local phone number",
        regex=re.compile(r"\(\s*\d{2,3}\s*\)\s*\d{3,5}-\d{4}"),
    ),
)

_UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _within_any(span: tuple[int, int], ranges: Sequence[tuple[int, int]]) -> bool:
    """Return ``True`` if ``span`` is fully contained inside one of ``ranges``."""

    start, end = span
    return any(r_start <= start and end <= r_end for r_start, r_end in ranges)


def validate_newsletter_privacy(newsletter_text: str) -> bool:
    """Ensure newsletter text does not contain phone number patterns."""

    uuid_spans = [(match.start(), match.end()) for match in _UUID_PATTERN.finditer(newsletter_text)]

    for pattern in _PHONE_PATTERNS:
        for match in pattern.regex.finditer(newsletter_text):
            span = match.span()
            if _within_any(span, uuid_spans):
                continue
            raise PrivacyViolationError(
                f"Possible phone number leak detected: {pattern.description}"
            )

    return True


__all__ = ["PrivacyViolationError", "validate_newsletter_privacy"]
