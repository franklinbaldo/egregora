"""PII (Personally Identifiable Information) detection and redaction utilities.

Centralizes regex patterns and scrubbing logic to ensure consistent privacy
handling across all input adapters and components.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig

# Basic PII patterns
# Matches email addresses (simple/common pattern)
EMAIL_PATTERN = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")

# Matches international and US phone numbers
# Handles: +1 123 456 7890, (123) 456-7890, 123-456-7890, etc.
# Expects at least 10 digits roughly.
PHONE_PATTERN = re.compile(r"(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")


def scrub_pii(text: str, config: EgregoraConfig | None = None) -> str:
    """Scrub PII from text based on configuration.

    Args:
        text: Input text to scrub
        config: Optional configuration object. If None, defaults to aggressive scrubbing (safe default).

    Returns:
        Text with PII replaced by redaction markers (e.g., <EMAIL_REDACTED>)

    """
    if config and not config.privacy.pii_detection_enabled:
        return text

    # Defaults if config is None or flags are true
    # If config is provided, respect its flags. If not, default to True (safe default).
    do_email = config.privacy.scrub_emails if config else True
    do_phone = config.privacy.scrub_phones if config else True

    if do_email:
        text = EMAIL_PATTERN.sub("<EMAIL_REDACTED>", text)
    if do_phone:
        text = PHONE_PATTERN.sub("<PHONE_REDACTED>", text)
    return text
