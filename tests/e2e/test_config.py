from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DateConfig:
    """Standardized dates for tests."""

    START: date = date(2023, 1, 1)
    END: date = date(2023, 12, 31)
    EXPORT_DATE: date = date(2024, 1, 15)
    VALID_FROM: date = date(2023, 1, 1)
    VALID_TO: date = date(2023, 12, 31)
    INVALID_FORMAT_2: str = "2023/01/01"


@dataclass(frozen=True)
class TimezoneConfig:
    """Standardized timezones for tests."""

    UTC: ZoneInfo = field(default_factory=lambda: ZoneInfo("UTC"))
    SAO_PAULO: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/Sao_Paulo"))
    VALID: ZoneInfo = field(default_factory=lambda: ZoneInfo("UTC"))
    INVALID: str = "Mars/Phobos"


@dataclass(frozen=True)
class TimeoutConfig:
    """Standardized timeouts for tests."""

    DEFAULT: float = 5.0
    LONG: float = 30.0
    RAG: float = 2.0


@dataclass(frozen=True)
class WindowConfig:
    """Standardized windowing configs for tests."""

    SIZE: int = 7
    UNIT: str = "days"


@dataclass
class WriteCommandOptions:
    """Options for the write command in tests."""

    from_date: date | str | None = None
    to_date: date | str | None = None
    timezone: ZoneInfo | str | None = None


def assert_command_success(result, expected_codes: tuple[int, ...] = (0,)):
    """Assertion helper for Typer commands."""
    assert result.exit_code in expected_codes, f"Command failed with output: {result.stdout}"


def build_write_command_args(zip_path: Path, output_dir: Path, options: WriteCommandOptions) -> list[str]:
    """Helper to build CLI arguments for the write command."""
    args = [str(zip_path), "--output-dir", str(output_dir)]

    if options.from_date:
        args.extend(["--from-date", str(options.from_date)])

    if options.to_date:
        args.extend(["--to-date", str(options.to_date)])

    if options.timezone:
        args.extend(["--timezone", str(options.timezone)])

    return args
