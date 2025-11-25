"""Centralized test configuration to reduce hardcoded values.

This module provides constants, fixtures, and helpers to make tests more
maintainable and reduce duplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


# =============================================================================
# Test Constants
# =============================================================================


@dataclass(frozen=True)
class TestTimeouts:
    """Timeout values for different test types."""

    DEFAULT: float = 60.0  # Default timeout for e2e tests
    SLOW: float = 90.0  # For complex tests like reader agent
    FAST: float = 30.0  # For simple unit-like tests


@dataclass(frozen=True)
class TestDates:
    """Common test dates in YYYY-MM-DD format."""

    VALID_FROM: str = "2025-10-01"
    VALID_TO: str = "2025-10-31"
    INVALID_FORMAT_1: str = "01-10-2025"  # Wrong format
    INVALID_FORMAT_2: str = "2025/10/31"  # Wrong separator


@dataclass(frozen=True)
class WindowConfig:
    """Default windowing configurations for testing."""

    DAYS_1: tuple[str, str] = ("1", "days")
    DAYS_7: tuple[str, str] = ("7", "days")
    HOURS_24: tuple[str, str] = ("24", "hours")
    MESSAGES_100: tuple[str, str] = ("100", "messages")


@dataclass(frozen=True)
class TestTimezones:
    """Common timezones for testing."""

    VALID: str = "America/New_York"
    INVALID: str = "Invalid/Timezone"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def default_write_args() -> dict[str, Any]:
    """Default arguments for write command testing.

    Returns a dictionary that can be easily modified for specific tests.
    """
    return {
        "step_size": "1",
        "step_unit": "days",
        "retrieval_mode": "exact",
        "enable_enrichment": False,
        "max_windows": 1,
    }


@pytest.fixture
def test_timeouts() -> TestTimeouts:
    """Provide timeout constants for tests."""
    return TestTimeouts()


@pytest.fixture
def test_dates() -> TestDates:
    """Provide test date constants."""
    return TestDates()


@pytest.fixture
def window_configs() -> WindowConfig:
    """Provide windowing configuration constants."""
    return WindowConfig()


@pytest.fixture
def test_timezones() -> TestTimezones:
    """Provide timezone constants."""
    return TestTimezones()


# =============================================================================
# Helper Functions
# =============================================================================


def build_write_command_args(
    test_zip_file: str,
    output_dir: str,
    *,
    step_size: str | None = None,
    step_unit: str | None = None,
    source_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    timezone: str | None = None,
    overlap: str | None = None,
    enable_enrichment: bool = True,
    retrieval_mode: str | None = None,
    max_windows: int | None = None,
    max_prompt_tokens: int | None = None,
) -> list[str]:
    """Build write command arguments with sensible defaults.

    This reduces duplication in tests by centralizing argument construction.

    Args:
        test_zip_file: Path to test ZIP file
        output_dir: Output directory path
        **kwargs: Optional command arguments

    Returns:
        List of command arguments ready for runner.invoke()
    """
    args = ["write", str(test_zip_file), "--output-dir", str(output_dir)]

    if step_size and step_unit:
        args.extend(["--step-size", step_size, "--step-unit", step_unit])

    if source_type:
        args.extend(["--source-type", source_type])

    if from_date:
        args.extend(["--from-date", from_date])

    if to_date:
        args.extend(["--to-date", to_date])

    if timezone:
        args.extend(["--timezone", timezone])

    if overlap:
        args.extend(["--overlap", overlap])

    if not enable_enrichment:
        args.append("--no-enable-enrichment")

    if retrieval_mode:
        args.extend(["--retrieval-mode", retrieval_mode])

    if max_windows is not None:
        args.extend(["--max-windows", str(max_windows)])

    if max_prompt_tokens is not None:
        args.extend(["--max-prompt-tokens", str(max_prompt_tokens)])

    return args


def assert_command_success(result, expected_codes: tuple[int, ...] = (0, 1)):
    """Assert command completed with acceptable exit code and provide helpful error.

    Args:
        result: CLI runner result
        expected_codes: Acceptable exit codes (default: 0 or 1)

    Raises:
        AssertionError: With detailed context if exit code is unexpected
    """
    assert result.exit_code in expected_codes, (
        f"Command exited with code {result.exit_code} (expected {expected_codes}).\n"
        f"Output (last 50 lines):\n{chr(10).join(result.stdout.split(chr(10))[-50:])}"
    )


def assert_directory_exists(path, context: str = ""):
    """Assert directory exists with helpful error message.

    Args:
        path: Path to check
        context: Additional context for error message
    """
    assert path.exists(), (
        f"Directory not found: {path}\n"
        f"{context}\n"
        f"Parent contents: {list(path.parent.iterdir()) if path.parent.exists() else 'N/A'}"
    )
