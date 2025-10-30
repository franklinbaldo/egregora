"""Privacy stage - Anonymization, PII detection, and opt-out management.

This package handles all privacy-related operations:
- UUID5-based anonymization of author names
- PII detection in text and media
- Opt-out user management
"""

from .anonymizer import anonymize_author, anonymize_mentions, anonymize_table
from .detector import PrivacyViolationError, validate_newsletter_privacy

__all__ = [
    # Anonymization
    "anonymize_author",
    "anonymize_table",
    "anonymize_mentions",
    # PII Detection
    "PrivacyViolationError",
    "validate_newsletter_privacy",
]
