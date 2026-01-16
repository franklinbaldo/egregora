from dataclasses import dataclass, field
from datetime import date
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DateConfig:
    """Standardized dates for tests."""

    START: date = date(2023, 1, 1)
    END: date = date(2023, 12, 31)
    EXPORT_DATE: date = date(2024, 1, 15)


@dataclass(frozen=True)
class TimezoneConfig:
    """Standardized timezones for tests."""

    UTC: ZoneInfo = field(default_factory=lambda: ZoneInfo("UTC"))
    SAO_PAULO: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/Sao_Paulo"))


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
