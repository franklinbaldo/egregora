"""Privacy configuration for tenant-scoped policies.

This module defines privacy policies that control:
- PII detection
- Media URL allowlisting
- Re-identification escrow
- Tenant isolation

Related ADR: docs/architecture/adr-003-privacy-gate-capability-token.md
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PrivacyConfig:
    """Privacy policy configuration (immutable, tenant-scoped).

    Attributes:
        tenant_id: Tenant identifier for multi-tenant isolation
        detect_pii: Enable PII detection (phones, emails, addresses)
        allowed_media_domains: Allowlist for media URLs
        enable_reidentification_escrow: Store author_raw → author_uuid mapping
        reidentification_retention_days: How long to keep escrow data

    Example:
        >>> config = PrivacyConfig(
        ...     tenant_id="acme-corp",
        ...     detect_pii=True,
        ...     allowed_media_domains=("acme.com", "trusted.com"),
        ... )

    """

    tenant_id: str
    """Tenant identifier for multi-tenant isolation."""

    detect_pii: bool = True
    """Enable PII detection (phones, emails, addresses)."""

    allowed_media_domains: tuple[str, ...] = ()
    """Allowlist for media URLs (e.g., ('example.com',))."""

    enable_reidentification_escrow: bool = False
    """Store author_raw → author_uuid mapping for re-identification.
    
    WARNING: Enabling this stores PII for re-identification. Only enable
    if you have explicit consent and compliance requirements.
    """

    reidentification_retention_days: int = 90
    """How long to keep re-identification escrow (default: 90 days)."""

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.tenant_id:
            raise ValueError("tenant_id cannot be empty")

        if self.reidentification_retention_days < 1:
            raise ValueError("reidentification_retention_days must be >= 1")
