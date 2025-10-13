"""Enrichment command for the Egregora CLI."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import polars as pl
import typer
from rich.console import Console
from rich.panel import Panel

from ..config import (
    AnonymizationConfig,
    CacheConfig,
    EnrichmentConfig,
    LLMConfig,
    PipelineConfig,
    ProfilesConfig,
)
from ..enrichment import ContentEnricher
from ..gemini_manager import GeminiManager
from ..rag.config import RAGConfig

MAX_ERRORS_TO_SHOW = 3

console = Console()


def enrich_command(
    url: Annotated[str, typer.Argument(..., help="URL ou caminho de mídia para enriquecer")],
    model: Annotated[str, typer.Option(None, "--model", help="Modelo Gemini para enriquecimento")],
    output_format: Annotated[
        str,
        typer.Option("pretty", "--format", "-f", help="Formato de saída: pretty, json"),
    ],
    save_cache: Annotated[
        bool,
        typer.Option(True, "--cache/--no-cache", help="Salvar resultado no cache"),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(False, "--dry-run", help="Simula enriquecimento sem chamadas da API"),
    ],
) -> None:
    """Testa o enriquecimento de uma URL ou mídia específica."""

    console.print(f"🔍 Testando enriquecimento: {url}")

    if dry_run:
        _enrich_dry_run(url, save_cache)
        return

    try:
        _enrich_url(url, model, output_format)
    except ImportError as e:
        console.print(f"❌ Dependência não encontrada: {e}")
        console.print("💡 Instale as dependências: uv sync")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Erro durante enriquecimento: {e}")
        raise typer.Exit(1) from e


def _enrich_dry_run(url: str, save_cache: bool) -> None:
    """Simulates enrichment without API calls."""
    console.print("🔍 Modo DRY RUN - Simulando enriquecimento")
    # Show what would be done without API calls
    if url.startswith(("http://", "https://")):
        console.print(
            Panel(
                f"[bold blue]📡 URL Enriquecimento (Simulado)[/bold blue]\n\n"
                f"[bold]URL:[/bold] {url}\n"
                f"[bold]Tipo:[/bold] Link da web\n"
                f"[bold]Análise:[/bold] Extrairia conteúdo, palavras-chave e resumo\n"
                f"[bold]APIs:[/bold] Gemini (content analysis)\n"
                f"[bold]Cache:[/bold] {'Habilitado' if save_cache else 'Desabilitado'}",
                title="Simulação de Enriquecimento",
                border_style="blue",
            )
        )
    else:
        media_path = Path(url)
        if media_path.exists():
            console.print(
                Panel(
                    f"[bold blue]🖼️ Mídia Enriquecimento (Simulado)[/bold blue]\n\n"
                    f"[bold]Arquivo:[/bold] {media_path.name}\n"
                    f"[bold]Tipo:[/bold] {media_path.suffix or 'Desconhecido'}\n"
                    f"[bold]Análise:[/bold] Análise de conteúdo visual/áudio\n"
                    f"[bold]APIs:[/bold] Gemini (multimodal analysis)\n"
                    f"[bold]Cache:[/bold] {'Habilitado' if save_cache else 'Desabilitado'}",
                    title="Simulação de Enriquecimento",
                    border_style="blue",
                )
            )
        else:
            console.print(f"❌ Arquivo não encontrado: {media_path}")
            raise typer.Exit(1)


def _enrich_url(url: str, model: str | None, output_format: str) -> None:
    """Enriches a URL."""
    config = PipelineConfig(
        zip_files=[],  # Not needed for enrichment testing
        model=model or "gemini-flash-lite-latest",
        llm=LLMConfig(),
        enrichment=EnrichmentConfig(),
        cache=CacheConfig(),
        profiles=ProfilesConfig(),
        anonymization=AnonymizationConfig(),
        rag=RAGConfig(),
    )

    # Create enricher
    gemini_manager = GeminiManager()
    enricher = ContentEnricher(config.enrichment, gemini_manager=gemini_manager)

    # Test if it's a URL or file path
    if url.startswith(("http://", "https://")):
        # It's a URL - create a minimal DataFrame for testing
        console.print(f"📡 Enriquecendo URL: {url}")

        # Create a minimal polars DataFrame with the URL in a message
        test_df = pl.DataFrame(
            {
                "timestamp": [datetime.now()],
                "sender": ["Test-User"],
                "message": [f"Confira este link: {url}"],
                "date": [datetime.now().date()],
            }
        )

        # Run enrichment on the DataFrame
        result = asyncio.run(enricher.enrich_dataframe(test_df, client=gemini_manager.client))

    else:
        # It's likely a file path
        media_path = Path(url)
        if not media_path.exists():
            console.print(f"❌ Arquivo não encontrado: {media_path}")
            raise typer.Exit(1)

        console.print(f"🖼️ Enriquecendo mídia: {media_path}")

        # Create a minimal DataFrame with media reference
        test_df = pl.DataFrame(
            {
                "timestamp": [datetime.now()],
                "sender": ["Test-User"],
                "message": [f"<Mídia oculta> {media_path.name}"],
                "date": [datetime.now().date()],
            }
        )

        result = asyncio.run(enricher.enrich_dataframe(test_df, client=gemini_manager.client))

    # Format output
    if output_format == "json":
        _format_json(result)
    else:
        _format_pretty(result)


def _format_json(result) -> None:
    """Formats the enrichment result as JSON."""
    metrics_dict = {}
    if result.metrics:
        metrics_dict = {
            "started_at": result.metrics.started_at.isoformat(),
            "finished_at": result.metrics.finished_at.isoformat(),
            "total_references": result.metrics.total_references,
            "analyzed_items": result.metrics.analyzed_items,
            "relevant_items": result.metrics.relevant_items,
            "error_count": result.metrics.error_count,
            "domains": result.metrics.domains,
            "threshold": result.metrics.threshold,
        }

    result_dict = {
        "items_count": len(result.items),
        "errors_count": len(result.errors),
        "duration_seconds": result.duration_seconds,
        "metrics": metrics_dict,
        "errors": result.errors if result.errors else [],
    }
    console.print(json.dumps(result_dict, indent=2, ensure_ascii=False))


def _format_pretty(result) -> None:
    """Formats the enrichment result in a pretty format."""
    relevant_items = result.relevant_items(2) if result.items else []
    console.print(
        Panel(
            f"[bold green]✅ Enriquecimento concluído[/bold green]\n\n"
            f"[bold]Itens processados:[/bold] {len(result.items)}\n"
            f"[bold]Itens relevantes:[/bold] {len(relevant_items)}\n"
            f"[bold]Erros:[/bold] {len(result.errors)}\n"
            f"[bold]Duração:[/bold] {result.duration_seconds:.2f}s",
            title="Resultado do Enriquecimento",
            border_style="green" if not result.errors else "yellow",
        )
    )

    if result.errors:
        console.print("\n[bold red]❌ Erros encontrados:[/bold red]")
        for error in result.errors[:MAX_ERRORS_TO_SHOW]:  # Show first 3
            console.print(f"  • {error}")
        if len(result.errors) > MAX_ERRORS_TO_SHOW:
            console.print(f"  ... e mais {len(result.errors) - MAX_ERRORS_TO_SHOW}")

    if relevant_items:
        console.print("\n[bold yellow]📋 Itens relevantes:[/bold yellow]")
        for item in relevant_items:  # Show all items
            ref = item.reference
            analysis = item.analysis
            console.print(f"  • {ref.url}")
            if analysis and analysis.summary:
                console.print(f"    {analysis.summary}")
            if analysis and analysis.topics:
                console.print(f"    [bold]Tópicos:[/bold] {', '.join(analysis.topics)}")
            if analysis and analysis.actions:
                console.print("    [bold]Ações:[/bold]")
                for action in analysis.actions:
                    console.print(f"      - {action.description}")
            if analysis:
                console.print(f"    [bold]Relevância:[/bold] {analysis.relevance}/5")
            console.print()  # Add spacing between items
