#!/usr/bin/env python3
"""Minimal enrichment run showcasing Gemini integration or the offline stub."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from egregora.config import EnrichmentConfig
from egregora.enrichment import ContentEnricher


class _OfflineModel:
    def __init__(self) -> None:
        payload = os.getenv(
            "FAKE_GEMINI_RESPONSE",
            json.dumps(
                {
                    "summary": "Resumo offline de exemplo para https://example.com.",
                    "key_points": [
                        "Demonstra fluxo sem depender da API.",
                        "Resultados são determinísticos para testes.",
                    ],
                    "tone": "informativo",
                    "relevance": 3,
                },
                ensure_ascii=False,
            ),
        )
        self._payload = payload

    def generate_content(self, model: str, contents: Any, config: Any) -> SimpleNamespace:
        part = SimpleNamespace(text=self._payload)
        content = SimpleNamespace(parts=[part])
        candidate = SimpleNamespace(content=content)
        return SimpleNamespace(text=self._payload, candidates=[candidate])


class _OfflineClient:
    def __init__(self) -> None:
        self.models = _OfflineModel()


def _ensure_types_stub() -> None:
    import egregora.enrichment as enrichment_module

    if enrichment_module.types is not None:
        return

    class _Part:
        def __init__(self, text: str | None = None, file_uri: str | None = None) -> None:
            self.text = text
            self.file_uri = file_uri

        @classmethod
        def from_text(cls, text: str) -> "_Part":
            return cls(text=text)

        @classmethod
        def from_uri(cls, file_uri: str) -> "_Part":
            return cls(file_uri=file_uri)

    class _Content:
        def __init__(self, role: str, parts: list[_Part]) -> None:
            self.role = role
            self.parts = parts

    class _GenerateContentConfig:
        def __init__(self, *, temperature: float, response_mime_type: str) -> None:
            self.temperature = temperature
            self.response_mime_type = response_mime_type

    enrichment_module.types = SimpleNamespace(
        Part=_Part,
        Content=_Content,
        GenerateContentConfig=_GenerateContentConfig,
    )


def _build_client() -> Any:
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if os.getenv("EGREGORA_ENRICHMENT_OFFLINE"):
        print("⚠️ Modo offline forçado via EGREGORA_ENRICHMENT_OFFLINE.")
        return _OfflineClient()
    if not api_key:
        print("⚠️ GEMINI_API_KEY ausente — executando em modo offline determinístico.")
        return _OfflineClient()

    try:
        from google import genai  # type: ignore
    except ModuleNotFoundError:
        print("⚠️ Pacote google-genai indisponível — executando em modo offline determinístico.")
        return _OfflineClient()

    return genai.Client(api_key=api_key)


async def _run_enrichment(client: Any, metrics_path: Path | None) -> int:
    config = EnrichmentConfig(
        enabled=True,
        max_links=2,
        relevance_threshold=2,
        metrics_csv_path=metrics_path,
    )
    enricher = ContentEnricher(config)

    transcript = "\n".join(
        [
            "09:00 - Alice: Olhem este artigo: https://example.com/guia",
            "09:05 - Bob: Outro link bacana https://example.org/detalhes",
        ]
    )
    result = await enricher.enrich([(date.today(), transcript)], client=client)
    relevant = result.relevant_items(config.relevance_threshold)

    if not relevant:
        print("❌ Enriquecimento executado, mas nenhum item atingiu o limiar configurado.")
        return 1

    print(
        "✅ {relevant}/{total} item(s) relevantes com duração de {duration:.2f}s.".format(
            relevant=len(relevant),
            total=len(result.items),
            duration=result.duration_seconds,
        )
    )
    prompt_section = result.format_for_prompt(config.relevance_threshold)
    if prompt_section:
        print("\n--- Seção pronta para o prompt ---")
        print(prompt_section)

    if result.metrics and config.metrics_csv_path:
        print(f"\n📊 Métricas registradas em {config.metrics_csv_path}")

    return 0


def main() -> int:
    _ensure_types_stub()
    metrics_override = os.getenv("EGREGORA_METRICS_PATH")
    metrics_path = Path(metrics_override) if metrics_override else Path("metrics/enrichment_run.csv")

    try:
        client = _build_client()
        return asyncio.run(_run_enrichment(client, metrics_path))
    except KeyboardInterrupt:
        print("⚠️ Execução interrompida pelo usuário.")
        return 1
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"❌ Falha ao executar o exemplo: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
