"""This module defines the regular expression patterns used for PII detection.

Separating patterns from the detection logic allows for easier management,
testing, and reuse of these regular expressions across different privacy-related
utilities. Each pattern is represented by a `PrivacyPattern` dataclass, which
includes a description and the compiled regex object.
"""
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class PrivacyPattern:
    """Represents a pattern for detecting a specific type of PII."""
    description: str
    regex: re.Pattern[str]

# Phone Number Patterns
PHONE_INTERNATIONAL = PrivacyPattern(
    description="international phone number",
    regex=re.compile(r"\\+\\d{2}\\s?\\d{2}\\s?\\d{4,5}-?\\d{4}")
)
PHONE_LOCAL_HYPHEN = PrivacyPattern(
    description="local phone number with hyphen",
    regex=re.compile(r"\\b\\d{3,5}-\\d{4}\\b")
)
PHONE_LOCAL_PARENTHESIZED = PrivacyPattern(
    description="parenthesized local phone number",
    regex=re.compile(r"\\(\\s*\\d{2,3}\\s*\\)\\s*\\d{3,5}-\\d{4}")
)

# Email Pattern
EMAIL_ADDRESS = PrivacyPattern(
    description="email address",
    regex=re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", re.IGNORECASE)
)

# Brazilian ID Patterns
BRAZILIAN_CPF = PrivacyPattern(
    description="CPF identifier",
    regex=re.compile(r"\\b\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2}\\b")
)
BRAZILIAN_CNPJ = PrivacyPattern(
    description="CNPJ identifier",
    regex=re.compile(r"\\b\\d{2}\\.\\d{3}\\.\\d{3}/\\d{4}-\\d{2}\\b")
)

# UUID Pattern (used for exclusion)
UUID_PATTERN = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

# Collections of patterns
PHONE_PATTERNS = (PHONE_INTERNATIONAL, PHONE_LOCAL_HYPHEN, PHONE_LOCAL_PARENTHESIZED)
BRAZILIAN_ID_PATTERNS = (BRAZILIAN_CPF, BRAZILIAN_CNPJ)
PII_PATTERNS = (*PHONE_PATTERNS, EMAIL_ADDRESS, *BRAZILIAN_ID_PATTERNS)
