"""Test configuration and helper utilities for E2E tests."""

from dataclasses import dataclass
from typing import Any, Sequence

from typer.testing import Result


@dataclass
class DateConfig:
    """Date configuration constants."""
    VALID_FROM: str = "2025-01-01"
    VALID_TO: str = "2025-01-31"
    INVALID_FORMAT_2: str = "2025/01/01"


@dataclass
class TimezoneConfig:
    """Timezone configuration constants."""
    VALID: str = "UTC"
    INVALID: str = "Invalid/Timezone"


@dataclass
class TimeoutConfig:
    """Timeout configuration constants."""
    short: int = 5
    medium: int = 15
    long: int = 30


@dataclass
class WindowConfig:
    """Windowing configuration constants."""
    step_size: int = 1
    step_unit: str = "days"


@dataclass
class WriteCommandOptions:
    """Options for the write command builder."""
    from_date: str | None = None
    to_date: str | None = None
    timezone: str | None = None


def build_write_command_args(
    zip_path: Any, output_dir: Any, options: WriteCommandOptions
) -> list[str]:
    """Build arguments for the write command."""
    args = ["write", str(zip_path), "--output-dir", str(output_dir)]
    if options.from_date:
        args.extend(["--from-date", options.from_date])
    if options.to_date:
        args.extend(["--to-date", options.to_date])
    if options.timezone:
        args.extend(["--timezone", options.timezone])
    return args


def assert_command_success(result: Result, expected_codes: Sequence[int] = (0, 1)) -> None:
    """Assert that the command succeeded (or failed gracefully)."""
    assert result.exit_code in expected_codes, (
        f"Command failed with exit code {result.exit_code}. Output:\n{result.stdout}"
    )
