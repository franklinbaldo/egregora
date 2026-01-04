"""Domain-specific constants and types for the agents module."""

from enum import Enum

# Egregora system author constants
# Used when Egregora generates content (PROFILE posts, ANNOUNCEMENT posts)
EGREGORA_UUID = "00000000-0000-0000-0000-000000000000"
EGREGORA_NAME = "Egregora"


class SystemIdentifier(str, Enum):
    """Special system identifiers used for generated content."""

    EGREGORA_AUTHOR = "egregora"
    ANONYMOUS_USER = "anonymous"
