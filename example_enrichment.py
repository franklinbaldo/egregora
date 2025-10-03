"""Standalone example demonstrating the content enrichment pipeline."""

from __future__ import annotations

import asyncio
from datetime import date

from egregora.config import EnrichmentConfig
from egregora.enrichment import ContentEnricher
from egregora.pipeline import create_client

SAMPLE_TRANSCRIPT = """
10:03 — Ana: Gente, viram esse artigo sobre cooperativismo digital? https://example.com/artigo
10:05 — Bruno: Também compartilhei esse vídeo ontem https://www.youtube.com/watch?v=dQw4w9WgXcQ
10:08 — Ana: <Mídia oculta>
""".strip()


async def main() -> None:
    transcripts = [(date.today(), SAMPLE_TRANSCRIPT)]
    enrichment_config = EnrichmentConfig()
    enricher = ContentEnricher(enrichment_config)

    try:
        client = create_client()
    except Exception as exc:
        print(
            "[Aviso] Não foi possível criar o cliente Gemini. Prosseguindo em modo offline:",
            exc,
        )
        client = None

    result = await enricher.enrich(transcripts, client=client)
    section = result.format_for_prompt(enrichment_config.relevance_threshold)

    if section:
        print("\nSeção pronta para ser adicionada ao prompt:")
        print(section)
    else:
        print("Nenhum conteúdo relevante identificado.")

    print(f"\nDuração total: {result.duration_seconds:.2f}s")

    if result.errors:
        print("\nOcorreram erros durante o enriquecimento:")
        for error in result.errors:
            print(" -", error)


if __name__ == "__main__":
    asyncio.run(main())
