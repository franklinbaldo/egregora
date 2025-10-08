"""LLM assisted classification of system and noisy messages."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pydantic import ValidationError

try:  # pragma: no cover - optional at runtime
    from pydantic_ai import Agent
    from pydantic_ai.models.gemini import GeminiModel
except Exception:  # pragma: no cover - keep runtime lean without optional deps
    Agent = None  # type: ignore[assignment]
    GeminiModel = None  # type: ignore[assignment]

from .cache_manager import CacheManager
from .llm_models import SystemMessageLabel

EXPECTED_AUTHOR_PAYLOAD_PARTS = 2


@dataclass(slots=True)
class ClassificationMetrics:
    """Usage telemetry gathered during classification."""

    total_lines: int = 0
    cache_hits: int = 0
    llm_calls: int = 0
    llm_failures: int = 0
    estimated_tokens: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "total_lines": self.total_lines,
            "cache_hits": self.cache_hits,
            "llm_calls": self.llm_calls,
            "llm_failures": self.llm_failures,
            "estimated_tokens": self.estimated_tokens,
        }


class SystemMessageClassifier:
    """Identify system/noise messages to keep prompts privacy first."""

    _CACHE_VERSION = "1.2"

    def __init__(
        self,
        *,
        cache_manager: CacheManager | None = None,
        model_name: str | None = None,
        max_llm_calls: int | None = None,
        token_budget: int | None = None,
        retry_attempts: int = 1,
    ) -> None:
        self._cache = cache_manager
        self._max_llm_calls = max_llm_calls if max_llm_calls is None else max(0, int(max_llm_calls))
        self._token_budget = token_budget if token_budget is None else max(0, int(token_budget))
        self._metrics = ClassificationMetrics()

        self._agent = self._create_agent(model_name=model_name, retries=retry_attempts)

    @property
    def metrics(self) -> dict[str, int]:
        """Return a snapshot of current usage metrics."""

        return self._metrics.as_dict()

    def filter_transcript(self, text: str) -> tuple[str, list[SystemMessageLabel]]:
        """Return ``text`` without system/noise lines and associated labels."""

        filtered_parts: list[str] = []
        labels: list[SystemMessageLabel] = []

        for chunk in text.splitlines(keepends=True):
            line = chunk.rstrip("\n")
            newline = "\n" if chunk.endswith("\n") else ""
            label = self._classify_line(line)
            labels.append(label)
            if label.should_discard():
                continue
            filtered_parts.append(line + newline)

        return "".join(filtered_parts), labels

    def _classify_line(self, line: str) -> SystemMessageLabel:
        self._metrics.total_lines += 1

        stripped = line.strip()
        if not stripped:
            return SystemMessageLabel(is_system=False, is_noise=True, reason="Linha vazia.")

        cached = self._from_cache(line)
        if cached is not None:
            self._metrics.cache_hits += 1
            return cached

        if not self._can_call_llm():
            neutral = SystemMessageLabel(
                is_system=False,
                is_noise=False,
                reason="Classificador heurístico neutro (LLM indisponível).",
            )
            self._store_cache(line, neutral)
            return neutral

        prompt = self._build_prompt(stripped)
        try:
            assert self._agent is not None  # for type-checkers
            result = self._agent.run_sync(prompt)
            label = result.output
            if not isinstance(label, SystemMessageLabel):
                raise ValidationError("output", SystemMessageLabel)
        except Exception:  # pragma: no cover - network/agent behaviour
            self._metrics.llm_failures += 1
            fallback = SystemMessageLabel(
                is_system=False,
                is_noise=False,
                reason="Falha ao consultar LLM; linha mantida.",
            )
            self._store_cache(line, fallback)
            return fallback

        self._metrics.llm_calls += 1
        estimated_tokens = self._estimate_tokens(prompt, stripped)
        self._metrics.estimated_tokens += estimated_tokens

        if label.should_discard() and self._looks_like_user_message(line):
            label = SystemMessageLabel(
                is_system=False,
                is_noise=False,
                reason="Conteúdo preservado para evitar falso-positivo.",
            )

        self._store_cache(line, label)
        return label

    def _from_cache(self, line: str) -> SystemMessageLabel | None:
        if not self._cache:
            return None
        record = self._cache.get(self._cache_key(line))
        if not record or record.get("version") != self._CACHE_VERSION:
            return None
        data = record.get("label")
        if not isinstance(data, dict):
            return None
        try:
            return SystemMessageLabel.model_validate(data)
        except ValidationError:
            return None

    def _store_cache(self, line: str, label: SystemMessageLabel) -> None:
        if not self._cache:
            return
        payload = {
            "version": self._CACHE_VERSION,
            "label": label.model_dump(),
        }
        try:
            self._cache.set(self._cache_key(line), payload)
        except Exception:  # pragma: no cover - cache failures should be safe
            return

    def _cache_key(self, line: str) -> str:
        digest = hashlib.sha256(line.casefold().encode("utf-8")).hexdigest()
        return f"https://classifier.egregora/{digest}"

    def _can_call_llm(self) -> bool:
        if self._agent is None:
            return False
        if self._max_llm_calls is not None and self._metrics.llm_calls >= self._max_llm_calls:
            return False
        if self._token_budget is not None and self._metrics.estimated_tokens >= self._token_budget:
            return False
        return True

    @staticmethod
    def _estimate_tokens(prompt: str, text: str) -> int:
        # Empirical approximation: 4 caracteres ~ 1 token
        return max(1, (len(prompt) + len(text)) // 4)

    @staticmethod
    def _build_prompt(line: str) -> str:
        return (
            "Classifique a mensagem a seguir de um chat do WhatsApp já anonimizado. "
            "Responda em JSON com os campos: is_system (true/false), is_noise (true/false) "
            "e reason (string curta explicando). Mensagem: "
            f"{line}"
        )

    @staticmethod
    def _create_agent(model_name: str | None, retries: int) -> Agent | None:
        if Agent is None or GeminiModel is None or not model_name:
            return None
        try:
            gemini_model = GeminiModel(model_name)
        except Exception:  # pragma: no cover - provider/runtime specific
            return None
        return Agent(
            model=gemini_model,
            output_type=SystemMessageLabel,
            system_prompt=(
                "Você atua como um classificador de mensagens do WhatsApp. "
                "Indique se a mensagem é do sistema (entrada automática), "
                "se é ruído/informação irrelevante e explique sucintamente a decisão."
            ),
            retries=max(1, int(retries)),
        )

    def _looks_like_user_message(self, line: str) -> bool:
        parts = line.split(":", 1)
        if len(parts) != EXPECTED_AUTHOR_PAYLOAD_PARTS:
            return False
        author, payload = parts
        return bool(author.strip() and payload.strip())


__all__ = ["SystemMessageClassifier", "ClassificationMetrics"]
