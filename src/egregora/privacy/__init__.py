"""Privacy stage - Anonymization and opt-out management.

This package handles all privacy-related operations:
- UUID5-based anonymization of author names
- Opt-out user management

Note: PII detection is handled via:
1. Structural anonymization (anonymizer.py) - runs BEFORE LLMs
2. LLM-native prevention (prompt templates) - instructs LLMs to avoid PII
3. Post-generation detection (agents/enricher.py) - checks for PII_DETECTED marker
"""

from egregora.privacy.anonymizer import anonymize_table

__all__ = [
    "anonymize_table",
]
