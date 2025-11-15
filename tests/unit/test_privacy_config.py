"""Tests for privacy configuration.

Tests verify that:
1. PrivacySettings is immutable
2. Validation catches invalid configs
3. Default values work correctly
"""

from __future__ import annotations

import uuid

import pytest

from egregora.privacy.config import PrivacySettings
from egregora.privacy.uuid_namespaces import NAMESPACE_AUTHOR


class TestPrivacyConfig:
    """Test PrivacySettings dataclass."""

    def test_privacy_config_is_frozen(self):
        """PrivacySettings is immutable (frozen dataclass)."""
        config = PrivacySettings(tenant_id="test")

        with pytest.raises(AttributeError):
            config.tenant_id = "modified"  # type: ignore[misc]

    def test_privacy_config_defaults(self):
        """PrivacySettings has sensible defaults."""
        config = PrivacySettings(tenant_id="test")

        assert config.tenant_id == "test"
        assert config.detect_pii is True
        assert config.allowed_media_domains == ()
        assert config.enable_reidentification_escrow is False
        assert config.reidentification_retention_days == 90
        assert config.author_namespace == NAMESPACE_AUTHOR

    def test_privacy_config_custom_values(self):
        """PrivacySettings accepts custom values."""
        config = PrivacySettings(
            tenant_id="acme-corp",
            detect_pii=False,
            allowed_media_domains=("acme.com", "trusted.com"),
            enable_reidentification_escrow=True,
            reidentification_retention_days=30,
            author_namespace=uuid.uuid5(uuid.NAMESPACE_DNS, "acme"),
        )

        assert config.tenant_id == "acme-corp"
        assert config.detect_pii is False
        assert config.allowed_media_domains == ("acme.com", "trusted.com")
        assert config.enable_reidentification_escrow is True
        assert config.reidentification_retention_days == 30
        assert config.author_namespace == uuid.uuid5(uuid.NAMESPACE_DNS, "acme")

    def test_privacy_config_rejects_empty_tenant_id(self):
        """PrivacySettings raises ValueError for empty tenant_id."""
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            PrivacySettings(tenant_id="")

    def test_privacy_config_rejects_invalid_retention_days(self):
        """PrivacySettings raises ValueError for retention_days < 1."""
        with pytest.raises(ValueError, match="reidentification_retention_days must be >= 1"):
            PrivacySettings(
                tenant_id="test",
                reidentification_retention_days=0,
            )

        with pytest.raises(ValueError, match="reidentification_retention_days must be >= 1"):
            PrivacySettings(
                tenant_id="test",
                reidentification_retention_days=-10,
            )

    def test_privacy_config_allows_minimal_retention(self):
        """PrivacySettings allows reidentification_retention_days=1."""
        config = PrivacySettings(
            tenant_id="test",
            reidentification_retention_days=1,
        )

        assert config.reidentification_retention_days == 1
