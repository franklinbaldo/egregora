"""Privacy utilities for Egregora."""

from __future__ import annotations

import re
import uuid
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)

# Basic PII patterns
EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
PHONE_PATTERN = re.compile(r'(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}')

def scrub_pii(text: str, config: EgregoraConfig | None = None) -> str:
    """Scrub PII from text."""
    if config and not config.privacy.pii_detection_enabled:
        return text

    # Defaults if config is None or flags are true
    # If config is provided, respect its flags. If not, default to True (safe default).
    do_email = config.privacy.scrub_emails if config else True
    do_phone = config.privacy.scrub_phones if config else True

    if do_email:
        text = EMAIL_PATTERN.sub('<EMAIL_REDACTED>', text)
    if do_phone:
        text = PHONE_PATTERN.sub('<PHONE_REDACTED>', text)
    return text

def anonymize_author(author_key: str, namespace: uuid.UUID) -> str:
    """Generate a consistent UUID for an author name/key."""
    return str(uuid.uuid5(namespace, author_key))
