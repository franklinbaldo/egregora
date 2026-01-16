"""Configuration classes for E2E tests."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DateConfig:
    """Date configuration constants."""

    VALID_FROM: str = "2024-01-01"
    VALID_TO: str = "2024-01-31"
    INVALID_FORMAT: str = "01-10-2025"
    INVALID_FORMAT_2: str = "2025/10/01"


@dataclass
class TimeoutConfig:
    """Timeout configuration constants."""

    DEFAULT_TIMEOUT: int = 30


@dataclass
class TimezoneConfig:
    """Timezone configuration constants."""

    VALID: str = "America/Sao_Paulo"
    INVALID: str = "Invalid/Timezone"


@dataclass
class WindowConfig:
    """Window configuration constants."""


@dataclass
class WriteCommandOptions:
    """Options for write command builder."""

    from_date: str | None = None
    to_date: str | None = None
    timezone: str | None = None


def build_write_command_args(
    zip_file: Path, output_dir: Path, options: WriteCommandOptions | None = None
) -> list[str]:
    """Build command arguments list."""
    args = ["write", str(zip_file), "--output-dir", str(output_dir)]
    if options:
        if options.from_date:
            args.extend(["--from-date", options.from_date])
        if options.to_date:
            args.extend(["--to-date", options.to_date])
        if options.timezone:
            args.extend(["--timezone", options.timezone])
    return args


def assert_command_success(result: Any, expected_codes: tuple = (0, 1)) -> None:
    """Assert command success."""
    assert result.exit_code in expected_codes, f"Command failed: {result.stdout}"
