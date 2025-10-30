"""Privacy stage - Anonymization, PII detection, and opt-out management.

This package handles all privacy-related operations:
- UUID5-based anonymization of author names
- PII detection in text and media
- Opt-out user management
"""

from .anonymizer import anonymize_author, anonymize_table, replace_mentions
from .detector import detect_pii_in_text, opt_out_users, validate_newsletter_privacy

__all__ = [
    # Anonymization
    "anonymize_author",
    "anonymize_table",
    "replace_mentions",
    # PII Detection
    "detect_pii_in_text",
    "opt_out_users",
    "validate_newsletter_privacy",
]
