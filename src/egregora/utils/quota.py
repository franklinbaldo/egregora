from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


class QuotaExceededError(RuntimeError):
    """Raised when the LLM quota limit is reached."""


@dataclass
class QuotaUsageRecord:
    date: str
    used: int = 0


class QuotaTracker:
    """Simple daily quota tracker persisted under .egregora/."""

    def __init__(self, storage_dir: Path, daily_limit: int) -> None:
        self.storage_path = storage_dir / "quota_usage.json"
        self.daily_limit = daily_limit
        self._record = QuotaUsageRecord(date=date.today().isoformat(), used=0)
        self._ensure_storage()
        self._load()

    @property
    def used(self) -> int:
        return self._record.used

    @property
    def remaining(self) -> int:
        return max(0, self.daily_limit - self.used)

    def _ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        if not self.storage_path.exists():
            self._save()
            return
        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self._save()
            return

        record_date = data.get("date")
        used = data.get("used", 0)
        today = date.today().isoformat()
        if record_date == today:
            self._record.used = int(used)
        else:
            self._record = QuotaUsageRecord(date=today, used=0)
        self._save()

    def _save(self) -> None:
        payload = {"date": self._record.date, "used": self._record.used}
        with self.storage_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def reserve(self, count: int = 1) -> None:
        """Reserve quota for `count` LLM requests."""
        if count < 1:
            return
        today = date.today().isoformat()
        if self._record.date != today:
            self._record = QuotaUsageRecord(date=today, used=0)
        if self._record.used + count > self.daily_limit:
            raise QuotaExceededError(
                f"Daily LLM quota exceeded ({self.daily_limit} requests/day). "
                f"Used {self._record.used}, requested {count}."
            )
        self._record.used += count
        self._save()
