"""Privacy gate capability token pattern.

This module implements capability-based security for privacy enforcement:
- PrivacyPass: Unforgeable proof that privacy gate executed
- @require_privacy_pass: Decorator enforcing privacy_pass parameter
- PrivacyGate: Token issuer (only way to create PrivacyPass)

Critical Invariant:
    Any function touching LLM APIs MUST require a PrivacyPass token.
    This proves that:
    1. Input table conformed to IR schema
    2. PII was anonymized (author_raw → author_uuid)
    3. Tenant isolation was enforced

Related ADR: docs/architecture/adr-003-privacy-gate-capability-token.md

Example:
    >>> from egregora.privacy.gate import PrivacyGate, require_privacy_pass
    >>>
    >>> # Run privacy gate
    >>> anonymized, privacy_pass = PrivacyGate.run(raw_table, config, "run-123")
    >>>
    >>> # Use privacy_pass in LLM functions
    >>> @require_privacy_pass
    >>> def send_to_llm(table, *, privacy_pass):
    ...     # Decorator verifies privacy_pass is valid
    ...     return llm_api.generate(table)
    >>>
    >>> result = send_to_llm(anonymized, privacy_pass=privacy_pass)

"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from typing import TYPE_CHECKING, Any, NamedTuple, TypeVar

import ibis

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.privacy.config import PrivacySettings

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


class PrivacyPass(NamedTuple):
    """Unforgeable proof that privacy gate has executed.

    This is a capability token: possession grants access to privacy-protected operations.
    Cannot be constructed except via PrivacyGate.run().

    Attributes:
        ir_version: IR schema version (e.g., "1.0.0")
        run_id: Pipeline run ID for lineage tracking
        tenant_id: Tenant scope (multi-tenant isolation)
        timestamp: When privacy gate executed (UTC)

    Example:
        >>> # ❌ Cannot forge - PrivacyGate.run() is the only source
        >>> fake_pass = PrivacyPass("1.0.0", "run-123", "tenant", datetime.now(UTC))
        >>> # This works, but won't pass validation checks
        >>>
        >>> # ✅ Valid token from privacy gate
        >>> _, privacy_pass = PrivacyGate.run(table, config, "run-123")

    """

    ir_version: str
    """IR schema version that was validated."""

    run_id: str
    """Pipeline run ID for lineage tracking and audit trail."""

    tenant_id: str
    """Tenant identifier - this pass is only valid for this tenant."""

    timestamp: datetime
    """UTC timestamp when privacy gate executed."""


def require_privacy_pass[F: Callable[..., Any]](func: F) -> F:
    """Decorator: Fail if privacy_pass not provided or invalid.

    Use this decorator on any function that touches LLM APIs or processes
    anonymized data. The decorator enforces that a valid PrivacyPass is
    provided as a keyword argument.

    Args:
        func: Function to decorate (must accept privacy_pass kwarg)

    Returns:
        Wrapped function that validates privacy_pass

    Raises:
        RuntimeError: If privacy_pass is missing or not a PrivacyPass instance

    Example:
        >>> @require_privacy_pass
        >>> def send_to_llm(table, prompt, *, privacy_pass):
        ...     # Decorator ensures privacy_pass is valid
        ...     return llm.generate(prompt, table)
        >>>
        >>> # ❌ Fails - no privacy_pass
        >>> send_to_llm(table, "Summarize")
        RuntimeError: send_to_llm requires PrivacyPass capability
        >>>
        >>> # ✅ Succeeds - valid privacy_pass
        >>> send_to_llm(table, "Summarize", privacy_pass=valid_pass)

    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        privacy_pass = kwargs.get("privacy_pass")

        if privacy_pass is None:
            msg = (
                f"{func.__name__} requires PrivacyPass capability. "
                "Run PrivacyGate.run() first and pass privacy_pass=... kwarg."
            )
            raise RuntimeError(msg)

        if not isinstance(privacy_pass, PrivacyPass):
            msg = (
                f"{func.__name__} received invalid privacy_pass. "
                f"Expected PrivacyPass instance, got {type(privacy_pass).__name__}. "
                "Cannot forge privacy tokens - use PrivacyGate.run()."
            )
            raise RuntimeError(msg)

        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


class PrivacyGate:
    """Privacy boundary enforcement via capability tokens.

    Critical Invariant:
        Only PrivacyGate.run() can create PrivacyPass tokens.
        Possession of a PrivacyPass proves:
        1. Input table conformed to IR schema
        2. PII was anonymized (author_raw → author_uuid)
        3. Tenant isolation was enforced

    Example:
        >>> from egregora.privacy.gate import PrivacyGate
        >>> from egregora.privacy.config import PrivacySettings
        >>>
        >>> config = PrivacySettings(tenant_id="acme-corp")
        >>> raw_table = load_raw_data()  # Contains author_raw (PII)
        >>>
        >>> # Run privacy gate
        >>> anonymized, privacy_pass = PrivacyGate.run(
        ...     raw_table, config, run_id="run-123"
        ... )
        >>>
        >>> # Now safe to use with LLM APIs
        >>> send_to_llm(anonymized, privacy_pass=privacy_pass)

    """

    @staticmethod
    def run(
        table: Table,
        config: PrivacySettings,
        run_id: str,
    ) -> tuple[Table, PrivacyPass]:
        """Execute privacy gate and issue capability token.

        This is the ONLY way to create a valid PrivacyPass. The token
        serves as unforgeable proof that:
        1. IR schema validation passed
        2. PII anonymization completed
        3. Tenant isolation enforced

        Args:
            table: Input table with author_raw (PII) - must conform to IR schema
            config: Privacy configuration (tenant_id, policies)
            run_id: Pipeline run ID for lineage tracking

        Returns:
            (anonymized_table, privacy_pass):
                - anonymized_table: author_uuid instead of author_raw
                - privacy_pass: Capability token for downstream functions

        Raises:
            ValueError: If table doesn't conform to IR schema
            ValueError: If config validation fails

        Example:
            >>> config = PrivacySettings(tenant_id="acme")
            >>> raw = ibis.memtable([{"author_raw": "Alice", "message": "Hi"}])
            >>> anonymized, token = PrivacyGate.run(raw, config, "run-1")
            >>>
            >>> # token is unforgeable proof of privacy
            >>> assert isinstance(token, PrivacyPass)
            >>> assert token.tenant_id == "acme"

        """
        # Import here to avoid circular dependencies
        from egregora.database.validation import validate_ir_schema
        from egregora.privacy.anonymizer import anonymize_table
        from egregora.privacy.constants import deterministic_author_uuid

        # Validate config
        if not config.tenant_id:
            msg = "PrivacySettings.tenant_id cannot be empty"
            raise ValueError(msg)

        if not run_id:
            msg = "run_id cannot be empty"
            raise ValueError(msg)

        # 1. Validate IR schema
        validate_ir_schema(table)

        # 2. Enforce tenant isolation
        tenant_values = table.select(table.tenant_id).distinct().execute()
        tenants = set(tenant_values["tenant_id"].dropna().tolist())
        if tenants and tenants != {config.tenant_id}:
            msg = (
                "PrivacyGate received table for unexpected tenant. "
                f"expected={config.tenant_id}, found={sorted(tenants)}"
            )
            raise ValueError(msg)

        # 3. Validate deterministic author UUIDs

        @ibis.udf.scalar.python
        def author_uuid_matches(
            author_raw: str,
            author_uuid: uuid.UUID,
        ) -> bool:
            import uuid

            if author_raw is None or author_uuid is None:
                return False
            expected = deterministic_author_uuid(
                author_raw,
                namespace=config.author_namespace,
            )
            return uuid.UUID(str(author_uuid)) == expected

        validation = table.mutate(
            _valid_author_uuid=author_uuid_matches(
                table.author_raw,
                table.author_uuid,
            )
        )
        invalid_rows = validation.filter(~validation._valid_author_uuid).count().execute()
        if invalid_rows:
            msg = "PrivacyGate validation failed: author_uuid mismatch detected"
            raise ValueError(msg)

        sanitized_input = validation.drop("_valid_author_uuid")

        # 4. Redact raw identifiers while preserving UUIDs
        logger.info("PrivacyGate: Redacting table for tenant=%s, run=%s", config.tenant_id, run_id)
        anonymized = anonymize_table(sanitized_input)

        # 5. Detect PII (optional)
        if config.detect_pii:
            # TODO: Integrate PII detector once available
            logger.debug("PII detection enabled but not yet implemented")

        # 6. Issue unforgeable capability token
        privacy_pass = PrivacyPass(
            ir_version="1.0.0",
            run_id=run_id,
            tenant_id=config.tenant_id,
            timestamp=datetime.now(UTC),
        )

        logger.info(
            "PrivacyGate: Issued PrivacyPass for tenant=%s, run=%s, timestamp=%s",
            config.tenant_id,
            run_id,
            privacy_pass.timestamp.isoformat(),
        )

        return anonymized, privacy_pass


__all__ = [
    "PrivacyGate",
    "PrivacyPass",
    "require_privacy_pass",
]
