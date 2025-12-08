"""Privacy configuration for input adapters (structural anonymization).

This module provides adapter-level privacy configuration for deterministic
preprocessing of raw input data before it enters the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from egregora.constants import AuthorPrivacyStrategy, MentionPrivacyStrategy, TextPIIStrategy

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig


@dataclass
class AdapterPrivacyConfig:
    """Privacy configuration for a specific adapter.

    Defines how structural anonymization should be applied to raw input data.
    This is Level 1 privacy (deterministic preprocessing) separate from
    Level 2 LLM-native PII prevention.
    """

    author_strategy: AuthorPrivacyStrategy = AuthorPrivacyStrategy.UUID_MAPPING
    mention_strategy: MentionPrivacyStrategy = MentionPrivacyStrategy.UUID_REPLACEMENT
    phone_strategy: TextPIIStrategy = TextPIIStrategy.REDACT
    email_strategy: TextPIIStrategy = TextPIIStrategy.REDACT

    @classmethod
    def from_egregora_config(cls, config: EgregoraConfig) -> AdapterPrivacyConfig:
        """Build adapter privacy config from global configuration.

        Args:
            config: Global Egregora configuration

        Returns:
            AdapterPrivacyConfig with strategies from global config

        """
        structural = config.privacy.structural
        return cls(
            author_strategy=structural.author_strategy,
            mention_strategy=structural.mention_strategy,
            phone_strategy=structural.phone_strategy,
            email_strategy=structural.email_strategy,
        )

    @classmethod
    def disabled(cls) -> AdapterPrivacyConfig:
        """Create a config with all privacy features disabled (for public data).

        Returns:
            AdapterPrivacyConfig with all strategies set to NONE

        """
        return cls(
            author_strategy=AuthorPrivacyStrategy.NONE,
            mention_strategy=MentionPrivacyStrategy.NONE,
            phone_strategy=TextPIIStrategy.NONE,
            email_strategy=TextPIIStrategy.NONE,
        )
