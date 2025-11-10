"""Tests for privacy configuration.

Tests verify that:
1. PrivacyConfig is immutable
2. Validation catches invalid configs
3. Default values work correctly
"""

from __future__ import annotations

import pytest

from egregora.privacy.config import PrivacyConfig


class TestPrivacyConfig:
    """Test PrivacyConfig dataclass."""

    def test_privacy_config_is_frozen(self):
        """PrivacyConfig is immutable (frozen dataclass)."""
        config = PrivacyConfig(tenant_id="test")

        with pytest.raises(AttributeError):
            config.tenant_id = "modified"  # type: ignore[misc]

    def test_privacy_config_defaults(self):
        """PrivacyConfig has sensible defaults."""
        config = PrivacyConfig(tenant_id="test")

        assert config.tenant_id == "test"
        assert config.detect_pii is True
        assert config.allowed_media_domains == ()
        assert config.enable_reidentification_escrow is False
        assert config.reidentification_retention_days == 90

    def test_privacy_config_custom_values(self):
        """PrivacyConfig accepts custom values."""
        config = PrivacyConfig(
            tenant_id="acme-corp",
            detect_pii=False,
            allowed_media_domains=("acme.com", "trusted.com"),
            enable_reidentification_escrow=True,
            reidentification_retention_days=30,
        )

        assert config.tenant_id == "acme-corp"
        assert config.detect_pii is False
        assert config.allowed_media_domains == ("acme.com", "trusted.com")
        assert config.enable_reidentification_escrow is True
        assert config.reidentification_retention_days == 30

    def test_privacy_config_rejects_empty_tenant_id(self):
        """PrivacyConfig raises ValueError for empty tenant_id."""
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            PrivacyConfig(tenant_id="")

    def test_privacy_config_rejects_invalid_retention_days(self):
        """PrivacyConfig raises ValueError for retention_days < 1."""
        with pytest.raises(ValueError, match="reidentification_retention_days must be >= 1"):
            PrivacyConfig(
                tenant_id="test",
                reidentification_retention_days=0,
            )

        with pytest.raises(ValueError, match="reidentification_retention_days must be >= 1"):
            PrivacyConfig(
                tenant_id="test",
                reidentification_retention_days=-10,
            )

    def test_privacy_config_allows_minimal_retention(self):
        """PrivacyConfig allows reidentification_retention_days=1."""
        config = PrivacyConfig(
            tenant_id="test",
            reidentification_retention_days=1,
        )

        assert config.reidentification_retention_days == 1
