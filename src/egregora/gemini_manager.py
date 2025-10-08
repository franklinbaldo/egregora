"""Centralized helper to manage Gemini usage, retries, and quotas."""

from __future__ import annotations

import asyncio
import os
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - optional dependency
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - graceful degradation when library is absent
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

__all__ = ["GeminiManager", "GeminiQuotaError", "GeminiUsageLimit"]


class GeminiQuotaError(RuntimeError):
    """Raised when a subsystem exceeds the configured Gemini quota."""


@dataclass(slots=True)
class GeminiUsageLimit:
    """Simple structure to hold per-subsystem limits."""

    max_calls: int | None = None
    budget_remaining: int | None = None

    def allows(self, current: int) -> bool:
        return self.max_calls is None or current < self.max_calls

    def consume(self) -> None:
        if self.budget_remaining is not None:
            self.budget_remaining = max(0, self.budget_remaining - 1)


class GeminiManager:
    """Shared controller for Gemini API usage with retry/backoff and quotas."""

    def __init__(
        self,
        *,
        retry_attempts: int = 3,
        minimum_retry_seconds: float = 30.0,
        usage_limits: dict[str, GeminiUsageLimit] | None = None,
        client: Any | None = None,
    ) -> None:
        if genai is None or types is None:
            raise RuntimeError(
                "A dependência opcional 'google-genai' não está instalada. "
                "Instale-a ou desative recursos que dependem do Gemini"
            )

        self._retry_attempts = max(int(retry_attempts), 1)
        self._minimum_retry_seconds = max(float(minimum_retry_seconds), 0.0)
        self._usage_limits = usage_limits or {}
        self._usage_counts: dict[str, int] = defaultdict(int)

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if client is not None:
            self._client = client
        else:
            if not api_key:
                raise RuntimeError("Defina GEMINI_API_KEY ou GOOGLE_API_KEY no ambiente.")
            self._client = genai.Client(api_key=api_key)

    @property
    def client(self):  # pragma: no cover - simple property
        return self._client

    def register_limit(self, subsystem: str, max_calls: int | None) -> None:
        self._usage_limits[subsystem] = GeminiUsageLimit(max_calls=max_calls)

    def usage(self, subsystem: str) -> int:
        return self._usage_counts.get(subsystem, 0)

    def remaining(self, subsystem: str) -> int | None:
        limit = self._usage_limits.get(subsystem)
        if limit is None or limit.max_calls is None:
            return None
        return max(0, limit.max_calls - self._usage_counts.get(subsystem, 0))

    async def generate_content(
        self,
        subsystem: str,
        *,
        model: str,
        contents: Iterable[types.Content],
        config: types.GenerateContentConfig,
        safety_settings: Iterable[types.SafetySetting] | None = None,
    ):
        self._ensure_quota(subsystem)

        attempt = 0
        last_exc: Exception | None = None
        contents = list(contents)
        safety_settings = list(safety_settings or [])

        while attempt < self._retry_attempts:
            attempt += 1
            try:
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=config,
                    safety_settings=safety_settings or None,
                )
                self._usage_counts[subsystem] += 1
                limit = self._usage_limits.get(subsystem)
                if limit:
                    limit.consume()
                return response
            except Exception as exc:  # pragma: no cover - API dependent
                last_exc = exc
                retry_delay = self._parse_retry_delay(exc)
                if "RESOURCE_EXHAUSTED" in str(exc):
                    if attempt >= self._retry_attempts:
                        raise GeminiQuotaError(str(exc)) from exc
                    await asyncio.sleep(max(retry_delay or 0.0, self._minimum_retry_seconds))
                else:
                    raise

        raise last_exc if last_exc else RuntimeError("Unknown Gemini error")

    def _ensure_quota(self, subsystem: str) -> None:
        limit = self._usage_limits.get(subsystem)
        if limit is None:
            return
        current = self._usage_counts.get(subsystem, 0)
        if not limit.allows(current):
            raise GeminiQuotaError(
                f"Limite de chamadas atingido para '{subsystem}' (máximo {limit.max_calls})."
            )

    @staticmethod
    def _parse_retry_delay(exc: Exception) -> float | None:
        message = str(exc)
        match = re.search(r"retryDelay['\"]?\s*[:=]\s*'?(\d+)(?:\.(\d+))?s", message)
        if match:
            whole, frac = match.group(1), match.group(2) or ""
            return float(f"{whole}.{frac}" if frac else whole)
        match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", message)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None
