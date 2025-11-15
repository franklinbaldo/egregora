"""Privacy stage - Anonymization, PII detection, and opt-out management.

This package handles all privacy-related operations:
- UUID5-based anonymization of author names
- PII detection in text and media
- Opt-out user management
"""

from egregora.privacy.anonymizer import anonymize_table
from egregora.privacy.detector import PrivacyViolationError, validate_text_privacy

__all__ = [
    "PrivacyViolationError",
    "anonymize_table",
    "validate_text_privacy",
]
