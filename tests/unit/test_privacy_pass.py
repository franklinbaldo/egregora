"""Unit tests for PrivacyPass capability token.

Tests the capability token pattern that enforces privacy gate execution
before any LLM processing.

Property tests validate:
- Decorator enforcement (functions fail without token)
- Token immutability
- Tenant isolation
- Audit logging

See: src/egregora/privacy/gate.py
"""

from datetime import datetime
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from egregora.privacy.config import PrivacyConfig
from egregora.privacy.gate import (
    PrivacyGate,
    PrivacyPass,
    require_privacy_pass,
)

# ============================================================================
# PrivacyPass Token Tests
# ============================================================================


def test_privacy_pass_creation():
    """PrivacyPass tokens are created correctly."""
    privacy_pass = PrivacyPass(
        ir_version="1.0.0",
        run_id="550e8400-e29b-41d4-a716-446655440000",
        tenant_id="default",
        timestamp=datetime(2025, 1, 8, 12, 0, 0),
    )

    assert privacy_pass.ir_version == "1.0.0"
    assert privacy_pass.run_id == "550e8400-e29b-41d4-a716-446655440000"
    assert privacy_pass.tenant_id == "default"
    assert privacy_pass.timestamp == datetime(2025, 1, 8, 12, 0, 0)


def test_privacy_pass_immutability():
    """PrivacyPass tokens are immutable (NamedTuple)."""
    privacy_pass = PrivacyPass(
        ir_version="1.0.0",
        run_id="test-run-123",
        tenant_id="default",
        timestamp=datetime.now(),
    )

    # NamedTuples are immutable
    with pytest.raises(AttributeError):
        privacy_pass.tenant_id = "hacked"  # type: ignore


def test_privacy_pass_repr():
    """PrivacyPass has human-readable repr for logging."""
    privacy_pass = PrivacyPass(
        ir_version="1.0.0",
        run_id="550e8400-e29b-41d4-a716-446655440000",
        tenant_id="acme-corp",
        timestamp=datetime(2025, 1, 8, 12, 0, 0),
    )

    repr_str = repr(privacy_pass)
    assert "acme-corp" in repr_str
    assert "550e8400" in repr_str  # First 8 chars of run_id
    assert "1.0.0" in repr_str


# ============================================================================
# Decorator Tests
# ============================================================================


def test_require_privacy_pass_with_valid_token():
    """Functions with valid PrivacyPass token execute successfully."""

    @require_privacy_pass
    def llm_function(message: str, *, privacy_pass: PrivacyPass) -> str:
        return f"Processed: {message}"

    privacy_pass = PrivacyPass(
        ir_version="1.0.0",
        run_id="test-run",
        tenant_id="default",
        timestamp=datetime.now(),
    )

    result = llm_function("hello", privacy_pass=privacy_pass)
    assert result == "Processed: hello"


def test_require_privacy_pass_without_token_fails():
    """Functions without PrivacyPass token fail at runtime."""

    @require_privacy_pass
    def llm_function(*, privacy_pass: PrivacyPass) -> str:
        return "This should not execute"

    # Missing privacy_pass kwarg
    with pytest.raises(RuntimeError) as exc_info:
        llm_function()

    assert "requires PrivacyPass capability" in str(exc_info.value)
    assert "llm_function" in str(exc_info.value)


def test_require_privacy_pass_with_wrong_type_fails():
    """Functions with wrong type for privacy_pass fail."""

    @require_privacy_pass
    def llm_function(*, privacy_pass: PrivacyPass) -> str:
        return "This should not execute"

    # Wrong type (None instead of PrivacyPass)
    with pytest.raises(RuntimeError) as exc_info:
        llm_function(privacy_pass=None)

    assert "requires PrivacyPass capability" in str(exc_info.value)
    assert "llm_function" in str(exc_info.value)


def test_require_privacy_pass_with_dict_fails():
    """Functions with dict instead of PrivacyPass fail."""

    @require_privacy_pass
    def llm_function(*, privacy_pass: PrivacyPass) -> str:
        return "This should not execute"

    # Wrong type (dict instead of PrivacyPass)
    fake_pass = {"ir_version": "1.0.0", "run_id": "fake"}

    with pytest.raises(RuntimeError) as exc_info:
        llm_function(privacy_pass=fake_pass)

    assert "received invalid privacy_pass" in str(exc_info.value)
    assert "dict" in str(exc_info.value)


# ============================================================================
# PrivacyConfig Tests
# ============================================================================


def test_privacy_config_defaults():
    """PrivacyConfig has sensible defaults."""
    config = PrivacyConfig(tenant_id="default")

    assert config.tenant_id == "default"
    assert config.detect_pii is True
    assert config.allowed_media_domains == ()
    assert config.enable_reidentification_escrow is False
    assert config.reidentification_retention_days == 90


def test_privacy_config_with_custom_values():
    """PrivacyConfig accepts custom values."""
    config = PrivacyConfig(
        tenant_id="acme-corp",
        detect_pii=True,
        allowed_media_domains=("acme.com", "cdn.example.com"),
        enable_reidentification_escrow=True,
        reidentification_retention_days=30,
    )

    assert config.tenant_id == "acme-corp"
    assert config.detect_pii is True
    assert config.allowed_media_domains == ("acme.com", "cdn.example.com")
    assert config.enable_reidentification_escrow is True
    assert config.reidentification_retention_days == 30


def test_privacy_config_reidentification_validation():
    """PrivacyConfig validation: retention days must be >= 1."""
    with pytest.raises(ValueError) as exc_info:
        PrivacyConfig(
            tenant_id="test",
            reidentification_retention_days=0,  # Invalid: must be >= 1
        )

    assert "reidentification_retention_days must be >= 1" in str(exc_info.value)


def test_privacy_config_immutability():
    """PrivacyConfig is frozen (immutable)."""
    config = PrivacyConfig(tenant_id="default")

    # Frozen dataclass prevents modification
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        config.tenant_id = "hacked"  # type: ignore


# ============================================================================
# Property Tests (Hypothesis)
# ============================================================================


@given(
    st.text(min_size=1, max_size=100),
    st.text(min_size=1, max_size=100),
)
def test_privacy_pass_with_random_values(tenant_id: str, run_id: str):
    """PrivacyPass works with any valid string values."""
    privacy_pass = PrivacyPass(
        ir_version="1.0.0",
        run_id=run_id,
        tenant_id=tenant_id,
        timestamp=datetime.now(),
    )

    # Basic properties
    assert privacy_pass.tenant_id == tenant_id
    assert privacy_pass.run_id == run_id
    assert privacy_pass.ir_version == "1.0.0"

    # Can be used in decorated functions
    @require_privacy_pass
    def test_func(*, privacy_pass: PrivacyPass) -> str:
        return privacy_pass.tenant_id

    result = test_func(privacy_pass=privacy_pass)
    assert result == tenant_id


@given(st.text(min_size=1))
def test_decorator_enforcement_is_consistent(message: str):
    """Decorator enforcement is consistent across calls."""

    @require_privacy_pass
    def process_message(msg: str, *, privacy_pass: PrivacyPass) -> str:
        return f"Processed: {msg}"

    privacy_pass = PrivacyPass(
        ir_version="1.0.0",
        run_id=str(uuid4()),
        tenant_id="test",
        timestamp=datetime.now(),
    )

    # Should succeed with valid token
    result1 = process_message(message, privacy_pass=privacy_pass)
    result2 = process_message(message, privacy_pass=privacy_pass)

    assert result1 == result2  # Consistent results
    assert result1 == f"Processed: {message}"

    # Should fail without token
    with pytest.raises(RuntimeError):
        process_message(message)


# ============================================================================
# Integration Tests (with mock table)
# ============================================================================


def test_privacy_gate_run_basic():
    """PrivacyGate.run() returns table + capability token."""
    import ibis

    # Create mock table with both author and author_raw
    # (Current anonymizer expects 'author', new IR v1 uses 'author_raw')
    table = ibis.memtable(
        [
            {"author": "Alice", "author_raw": "Alice", "message": "Hello world"},
            {"author": "Bob", "author_raw": "Bob", "message": "Hi there"},
        ]
    )

    config = PrivacyConfig(tenant_id="default")
    run_id = str(uuid4())

    # Run privacy gate
    anon_table, privacy_pass = PrivacyGate.run(table, config, run_id)

    # Check capability token
    assert isinstance(privacy_pass, PrivacyPass)
    assert privacy_pass.ir_version == "1.0.0"
    assert privacy_pass.run_id == run_id
    assert privacy_pass.tenant_id == "default"

    # Check table is returned
    assert anon_table is not None
    # Current anonymizer modifies 'author', not 'author_raw'
    # This will change when we update anonymizer.py
    assert "message" in anon_table.columns


def test_privacy_gate_missing_required_columns():
    """PrivacyGate.run() fails if table missing required columns."""
    import ibis
    from ibis.common.exceptions import IbisTypeError

    # Table missing 'author' column
    table = ibis.memtable([{"message": "Hello"}])

    config = PrivacyConfig(tenant_id="default")
    run_id = str(uuid4())

    # Anonymizer expects 'author' column
    with pytest.raises(IbisTypeError) as exc_info:
        PrivacyGate.run(table, config, run_id)

    assert "Column 'author' is not found in table" in str(exc_info.value)


def test_privacy_pass_can_be_passed_through_pipeline():
    """PrivacyPass token can be passed through pipeline functions."""

    @require_privacy_pass
    def stage_1(data: str, *, privacy_pass: PrivacyPass) -> str:
        return f"Stage1: {data}"

    @require_privacy_pass
    def stage_2(data: str, *, privacy_pass: PrivacyPass) -> str:
        return f"Stage2: {data}"

    # Create token
    privacy_pass = PrivacyPass(
        ir_version="1.0.0",
        run_id="pipeline-run-123",
        tenant_id="default",
        timestamp=datetime.now(),
    )

    # Pass through pipeline
    result1 = stage_1("data", privacy_pass=privacy_pass)
    result2 = stage_2(result1, privacy_pass=privacy_pass)

    assert result2 == "Stage2: Stage1: data"


# ============================================================================
# Edge Cases
# ============================================================================


def test_privacy_pass_with_empty_strings():
    """PrivacyPass handles empty strings."""
    privacy_pass = PrivacyPass(
        ir_version="",
        run_id="",
        tenant_id="",
        timestamp=datetime.now(),
    )

    # Still valid (validation is caller's responsibility)
    assert privacy_pass.ir_version == ""
    assert privacy_pass.run_id == ""
    assert privacy_pass.tenant_id == ""


def test_decorator_preserves_function_metadata():
    """@require_privacy_pass preserves function name and docstring."""

    @require_privacy_pass
    def my_function(*, privacy_pass: PrivacyPass) -> str:
        """This is my function docstring."""
        return "ok"

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "This is my function docstring."


def test_multiple_decorators_work_together():
    """@require_privacy_pass works with other decorators."""
    import functools

    def log_calls(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print(f"Calling {func.__name__}")
            return func(*args, **kwargs)

        return wrapper

    @log_calls
    @require_privacy_pass
    def my_function(*, privacy_pass: PrivacyPass) -> str:
        return "ok"

    privacy_pass = PrivacyPass(
        ir_version="1.0.0",
        run_id="test",
        tenant_id="default",
        timestamp=datetime.now(),
    )

    result = my_function(privacy_pass=privacy_pass)
    assert result == "ok"
