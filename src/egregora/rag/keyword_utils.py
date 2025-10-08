"""Keyword extraction helpers that delegate semantic work to LLM providers."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

__all__ = [
    "KeywordExtractor",
    "KeywordProvider",
    "build_llm_keyword_provider",
]


class KeywordProvider(Protocol):
    """Callable responsible for producing semantic keywords from text."""

    def __call__(self, text: str, *, max_keywords: int) -> Sequence[str]:
        ...


def _normalise_keywords(values: Sequence[str], limit: int) -> list[str]:
    """Return a deduplicated, cleaned keyword list limited to ``limit`` items."""

    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        lowered = cleaned.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


@dataclass(slots=True)
class KeywordExtractor:
    """High-level keyword extractor that delegates to a :class:`KeywordProvider`."""

    max_keywords: int
    keyword_provider: KeywordProvider | None = None

    def __post_init__(self) -> None:
        if self.max_keywords < 1:
            raise ValueError("max_keywords must be at least 1")

    def extract(
        self,
        text: str,
        *,
        keyword_provider: KeywordProvider | None = None,
    ) -> list[str]:
        """Return semantic keywords for ``text`` using the configured provider."""

        provider = keyword_provider or self.keyword_provider
        if provider is None:
            raise RuntimeError(
                "KeywordExtractor requires a keyword_provider callable to operate"
            )

        if not text or not text.strip():
            return []

        raw_keywords = provider(text, max_keywords=self.max_keywords)
        return _normalise_keywords(raw_keywords, self.max_keywords)


def build_llm_keyword_provider(
    client: object,
    *,
    model: str,
    system_instruction: str | None = None,
) -> KeywordProvider:
    """Return a provider that asks a Gemini model to extract keywords."""

    try:
        from google.genai import types as genai_types  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "google-genai must be installed to build an LLM keyword provider"
        ) from exc

    base_instruction = system_instruction or (
        "Você é um assistente que identifica até N palavras-chave únicas em uma "
        "conversa do WhatsApp. Responda sempre em JSON com o formato "
        "{\"keywords\": [\"palavra\", ...]} e nunca inclua comentários adicionais."
    )

    def _provider(text: str, *, max_keywords: int) -> list[str]:
        if max_keywords < 1:
            return []

        prompt = (
            "Considere a conversa abaixo e retorne até "
            f"{max_keywords} palavras-chave distintas ordenadas por relevância.\n"
            "Texto:\n"
            f"{text.strip()}"
        )

        contents = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=prompt)],
            )
        ]

        config = genai_types.GenerateContentConfig(
            system_instruction=[genai_types.Part.from_text(text=base_instruction)],
            response_mime_type="application/json",
        )

        response = client.models.generate_content(  # type: ignore[call-arg]
            model=model,
            contents=contents,
            config=config,
        )

        payload_text = ""
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                if getattr(part, "text", None):
                    payload_text += part.text

        if not payload_text and getattr(response, "text", None):
            payload_text = str(response.text)

        if not payload_text:
            return []

        try:
            decoded = json.loads(payload_text)
        except json.JSONDecodeError:
            return []

        keywords = decoded.get("keywords", []) if isinstance(decoded, dict) else []
        if not isinstance(keywords, Sequence):
            return []

        return _normalise_keywords(
            [value if isinstance(value, str) else str(value) for value in keywords],
            max_keywords,
        )

    return _provider
