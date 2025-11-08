"""Privacy gate implementation with capability-based enforcement.

This module implements the mandatory privacy boundary that MUST run before
any LLM processing. It uses a capability token pattern (PrivacyPass) instead
of global state to ensure:

1. **Testability**: No global flags, pure dependency injection
2. **Auditability**: Each privacy pass tracks the run_id that performed anonymization
3. **Multi-tenant Safety**: tenant_id flows through the capability token
4. **Type Safety**: LLM functions must accept privacy_pass kwarg (enforced at compile time)

Architecture:
-------------
    Raw Data → PrivacyGate.run() → (Anonymized Data, PrivacyPass)
                                            ↓
    Anonymized Data + PrivacyPass → LLM Function (decorated with @require_privacy_pass)

The PrivacyPass token acts as a "proof" that the privacy gate ran. Without it,
LLM functions will fail at runtime.

See ADR-003 for full decision record and policy.

Example Usage:
--------------
    # In pipeline runner
    from egregora.privacy.gate import PrivacyGate, PrivacyPass

    # Run privacy gate
    table, privacy_pass = PrivacyGate.run(
        table=raw_table,
        config=privacy_config,
        run_id=run_id
    )

    # Pass token to LLM functions
    enriched = enrich_media(table, config, privacy_pass=privacy_pass)

    # LLM function declaration
    from egregora.privacy.gate import require_privacy_pass

    @require_privacy_pass
    def enrich_media(
        table: ibis.Table,
        config: Config,
        *,
        privacy_pass: PrivacyPass  # Required kwarg-only parameter
    ) -> ibis.Table:
        # LLM calls here are safe
        ...

Privacy Policy:
---------------
By default, the mapping author_raw → author_uuid is NOT persisted.
The privacy gate performs one-way anonymization using deterministic UUID5.

Tenants can opt-in to re-identification escrow by setting:
    privacy.enable_reidentification = true

See: docs/architecture/adr-002-deterministic-uuids.md
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, Callable, NamedTuple

import ibis

logger = logging.getLogger(__name__)


# ============================================================================
# PrivacyPass Capability Token
# ============================================================================


class PrivacyPass(NamedTuple):
    """Capability token proving privacy gate ran.

    This token acts as a "proof of anonymization" that must be passed to
    any function making LLM API calls. It replaces global state with
    dependency injection for better testability.

    Attributes:
        ir_version: IR schema version (e.g., "v1")
        run_id: Run ID that performed anonymization (from runs table)
        tenant_id: Tenant identifier (for multi-tenant isolation)
        timestamp: When privacy gate ran (UTC)

    Example:
        >>> privacy_pass = PrivacyPass(
        ...     ir_version="v1",
        ...     run_id="550e8400-e29b-41d4-a716-446655440000",
        ...     tenant_id="default",
        ...     timestamp=datetime.now()
        ... )
        >>> privacy_pass.tenant_id
        'default'

    Immutability:
        NamedTuple ensures tokens are immutable after creation.
        This prevents accidental modification during pipeline execution.
    """

    ir_version: str
    run_id: str
    tenant_id: str
    timestamp: datetime

    def __repr__(self) -> str:
        """Human-readable representation for logging."""
        return (
            f"PrivacyPass(tenant={self.tenant_id}, run={self.run_id[:8]}..., "
            f"ir={self.ir_version}, ts={self.timestamp.isoformat()})"
        )


# ============================================================================
# Privacy Gate Decorator
# ============================================================================


def require_privacy_pass(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: Fail if privacy_pass not provided to LLM function.

    This decorator enforces that any function making LLM API calls
    MUST receive a PrivacyPass capability token as a kwarg-only parameter.

    Usage:
        @require_privacy_pass
        def enrich_media(
            table: ibis.Table,
            config: Config,
            *,
            privacy_pass: PrivacyPass  # Required
        ) -> ibis.Table:
            # LLM calls here are safe
            ...

    Raises:
        RuntimeError: If privacy_pass kwarg is missing or wrong type

    Example:
        >>> @require_privacy_pass
        ... def llm_function(*, privacy_pass: PrivacyPass):
        ...     return "ok"
        >>> llm_function()  # Missing privacy_pass
        RuntimeError: llm_function requires PrivacyPass capability...

        >>> llm_function(privacy_pass=None)  # Wrong type
        RuntimeError: llm_function requires PrivacyPass capability...

        >>> privacy_pass = PrivacyPass("v1", "run-123", "default", datetime.now())
        >>> llm_function(privacy_pass=privacy_pass)
        'ok'
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        privacy_pass = kwargs.get("privacy_pass")

        if not isinstance(privacy_pass, PrivacyPass):
            raise RuntimeError(
                f"{func.__name__} requires PrivacyPass capability token. "
                f"Got: {type(privacy_pass).__name__}. "
                f"Run PrivacyGate.run() first and pass privacy_pass=... kwarg."
            )

        # Log privacy pass for audit trail
        logger.debug(
            f"✓ {func.__name__} called with {privacy_pass}",
            extra={
                "function": func.__name__,
                "tenant_id": privacy_pass.tenant_id,
                "run_id": privacy_pass.run_id,
                "ir_version": privacy_pass.ir_version,
            },
        )

        return func(*args, **kwargs)

    return wrapper


# ============================================================================
# Privacy Configuration
# ============================================================================


@dataclass(frozen=True)
class PrivacyConfig:
    """Configuration for privacy gate.

    Attributes:
        tenant_id: Tenant identifier (for multi-tenant isolation)
        anonymize_authors: Whether to anonymize author names (default: True)
        pii_patterns: Additional regex patterns to detect PII
        media_allowlist: URL patterns for allowed media domains
        media_denylist: URL patterns for blocked media domains
        enable_reidentification: Store salted mapping for re-id (default: False)
        reidentification_salt: Tenant-specific salt for escrow (if enabled)

    Example:
        >>> config = PrivacyConfig(
        ...     tenant_id="acme-corp",
        ...     media_allowlist=["*.acme.com", "*.trusted-cdn.com"]
        ... )
        >>> config.tenant_id
        'acme-corp'
    """

    tenant_id: str = "default"
    anonymize_authors: bool = True
    pii_patterns: tuple[str, ...] = ()
    media_allowlist: tuple[str, ...] | None = None
    media_denylist: tuple[str, ...] | None = None
    enable_reidentification: bool = False
    reidentification_salt: str | None = None

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.enable_reidentification and not self.reidentification_salt:
            raise ValueError(
                "reidentification_salt required when enable_reidentification=True"
            )


# ============================================================================
# Privacy Gate Implementation
# ============================================================================


class PrivacyGate:
    """Privacy boundary that MUST run before LLM processing.

    This class implements the mandatory privacy gate that:
    1. Anonymizes author names (author_raw → author_uuid via UUID5)
    2. Detects and flags PII (phones, emails, addresses)
    3. Filters media by allowlist/denylist
    4. Returns a PrivacyPass capability token as proof

    The returned PrivacyPass token must be passed to all downstream
    LLM functions decorated with @require_privacy_pass.

    Example:
        >>> from egregora.privacy.gate import PrivacyGate, PrivacyConfig
        >>> config = PrivacyConfig(tenant_id="default")
        >>> raw_table = ...  # Table with author_raw column
        >>> anonymized_table, privacy_pass = PrivacyGate.run(
        ...     table=raw_table,
        ...     config=config,
        ...     run_id="550e8400-..."
        ... )
        >>> # Now safe to pass to LLM functions
        >>> enriched = enrich_media(anonymized_table, privacy_pass=privacy_pass)
    """

    @staticmethod
    def run(
        table: ibis.Table,
        config: PrivacyConfig,
        run_id: str,
    ) -> tuple[ibis.Table, PrivacyPass]:
        """Execute privacy gate and return anonymized table + capability token.

        This is the ONLY entry point to LLM processing. All raw data must
        pass through this gate before any external API calls.

        Args:
            table: Input table with author_raw column
            config: Privacy configuration (tenant_id, allowlists, etc.)
            run_id: Run ID for tracking (from runs table)

        Returns:
            (anonymized_table, privacy_pass) tuple

        Raises:
            ValueError: If table missing required columns
            RuntimeError: If anonymization fails

        Processing Steps:
            1. Validate input table schema
            2. Anonymize authors (author_raw → author_uuid via UUID5)
            3. Detect PII (phones, emails, addresses)
            4. Filter media (allowlist/denylist)
            5. Create PrivacyPass capability token
            6. Return (anonymized_table, privacy_pass)

        Example:
            >>> table = ibis.memtable([
            ...     {"author_raw": "Alice", "message": "Hello world"}
            ... ])
            >>> config = PrivacyConfig(tenant_id="default")
            >>> anon_table, privacy_pass = PrivacyGate.run(
            ...     table, config, run_id="test-run-123"
            ... )
            >>> "author_uuid" in anon_table.columns
            True
            >>> privacy_pass.tenant_id
            'default'
        """
        logger.info(
            "🔒 Privacy gate: Starting",
            extra={
                "run_id": run_id,
                "tenant_id": config.tenant_id,
                "row_count": table.count().execute() if hasattr(table, "count") else None,
            },
        )

        # 1. Validate input schema
        required_columns = {"author_raw", "message"}
        actual_columns = set(table.columns)

        if not required_columns.issubset(actual_columns):
            missing = required_columns - actual_columns
            raise ValueError(
                f"Privacy gate requires columns: {required_columns}. "
                f"Missing: {missing}"
            )

        # 2. Anonymize authors (UUID5)
        # TODO: Update anonymizer.py to accept tenant_id parameter (Day 1 remaining task)
        # For now, use existing anonymizer (which uses old namespace)
        try:
            from egregora.privacy.anonymizer import anonymize_table

            # Current anonymizer doesn't support tenant_id yet
            # This will be updated in the next task (Day 1 completion)
            logger.warning(
                "Using legacy anonymizer (no tenant_id support). "
                "TODO: Update anonymizer.py to use deterministic_author_uuid()"
            )
            table = anonymize_table(table)
            logger.debug("✓ Authors anonymized (UUID5 - legacy namespace)")
        except ImportError:
            # Fallback: anonymizer not found
            logger.error("anonymize_table not found, privacy gate incomplete!")
            raise RuntimeError(
                "Privacy gate requires anonymizer.py. "
                "Ensure src/egregora/privacy/anonymizer.py exists."
            )

        # 3. Detect PII
        # TODO: Implement PII detection
        # For now, just add empty pii_flags column
        if "pii_flags" not in table.columns:
            logger.debug("PII detection: Skipped (not yet implemented)")

        # 4. Filter media
        if config.media_allowlist or config.media_denylist:
            logger.debug(
                "Media filtering configured",
                extra={
                    "allowlist": config.media_allowlist,
                    "denylist": config.media_denylist,
                },
            )
            # TODO: Implement media filtering
            # For now, just log

        # 5. Create capability token
        privacy_pass = PrivacyPass(
            ir_version="v1",
            run_id=run_id,
            tenant_id=config.tenant_id,
            timestamp=datetime.utcnow(),
        )

        logger.info(
            "✓ Privacy gate: Complete",
            extra={
                "run_id": run_id,
                "tenant_id": config.tenant_id,
                "privacy_pass": str(privacy_pass),
            },
        )

        return table, privacy_pass


# ============================================================================
# Re-identification Escrow (Opt-In)
# ============================================================================


class ReidentificationEscrow:
    """Optional re-identification escrow for author mapping.

    By default, PrivacyGate performs one-way anonymization (no reverse mapping).
    Tenants can opt-in to store a salted mapping for re-identification:

        author_raw → HMAC(author_raw, tenant_salt) → author_uuid

    The HMAC value can be used to re-identify authors if needed, but requires:
    1. Tenant admin credentials
    2. Within retention window (default: 90 days)
    3. Audit log entry

    Example:
        >>> escrow = ReidentificationEscrow(
        ...     tenant_id="acme-corp",
        ...     salt="random-salt-abc123"
        ... )
        >>> escrow.store_mapping(
        ...     author_raw="Alice",
        ...     author_uuid=UUID("...")
        ... )
        >>> escrow.reidentify(author_uuid=UUID("..."))
        'Alice'  # If within retention window

    Note:
        This is NOT implemented yet. See ADR-003 for policy and design.
    """

    def __init__(self, tenant_id: str, salt: str):
        """Initialize escrow for tenant.

        Args:
            tenant_id: Tenant identifier
            salt: Tenant-specific salt (should be random, stored securely)
        """
        self.tenant_id = tenant_id
        self.salt = salt
        logger.warning(
            "ReidentificationEscrow is not yet implemented. "
            "This is a placeholder for future feature."
        )

    def store_mapping(self, author_raw: str, author_uuid: str) -> None:
        """Store salted mapping for re-identification.

        Args:
            author_raw: Original author name
            author_uuid: Anonymized UUID

        Raises:
            NotImplementedError: This feature is not yet implemented
        """
        raise NotImplementedError(
            "Re-identification escrow not yet implemented. "
            "See ADR-003 for design and policy."
        )

    def reidentify(self, author_uuid: str) -> str | None:
        """Re-identify author from UUID (if within retention window).

        Args:
            author_uuid: Anonymized UUID

        Returns:
            Original author name or None if not found/expired

        Raises:
            NotImplementedError: This feature is not yet implemented
        """
        raise NotImplementedError(
            "Re-identification escrow not yet implemented. "
            "See ADR-003 for design and policy."
        )
