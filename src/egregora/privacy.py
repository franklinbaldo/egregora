"""Privacy utilities to guard against personal data leaks."""

from __future__ import annotations

import re
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
# deliberately conservative; if a pattern matches we prefer to fail fast and
# surface an explicit error to the caller.
_PHONE_PATTERNS: tuple[_PrivacyPattern, ...] = (
    _PrivacyPattern(
        description="international phone number",
        regex=re.compile(r"\+\d{2}\s?\d{2}\s?\d{4,5}-?\d{4}"),
    ),
    _PrivacyPattern(
        description="partial phone number (4-5 digits)",
        # Exclude common years from this check to avoid false positives
        regex=re.compile(r"\b(?!19\d{2}|20\d{2})\d{4,5}\b"),
    ),
)


def validate_newsletter_privacy(newsletter_text: str) -> bool:
    """Ensure newsletter text does not contain phone number patterns."""

    for pattern in _PHONE_PATTERNS:
        if pattern.regex.search(newsletter_text):
            raise PrivacyViolationError(
                f"Possible phone number leak detected: {pattern.description}"
            )

    return True


__all__ = ["PrivacyViolationError", "validate_newsletter_privacy"]
