"""Enhanced command line interface for Egregora with subcommands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .ingest.main import app as ingest_app
from .rag_context.main import app as rag_app
from .archive.main import app as archive_app
from .embed.main import app as embed_app
from .config import PipelineConfig, RAGConfig
from .processor import UnifiedProcessor
from .static.builder import StaticSiteBuilder

MAX_POSTS_TO_SHOW = 3
MAX_DATES_TO_SHOW = 10
QUOTA_WARNING_THRESHOLD = 200
QUOTA_WARNING_THRESHOLD_ENRICH = 15

console = Console()
app = typer.Typer(help="Egregora - WhatsApp to post pipeline with AI enrichment")


# Create a new typer app for the "gen" subcommand
gen_app = typer.Typer(help="Gera posts, enriquece e opcionalmente constrói o site estático.")


@gen_app.callback()
def gen_callback() -> None:
    """Funções de geração de conteúdo."""
    ...


@gen_app.command("run")
def generate_run(
    zip_file: Path = typer.Argument(..., help="Caminho para o arquivo ZIP do WhatsApp."),
    inject_rag: bool = typer.Option(False, "--inject-rag", help="Injeta contexto RAG."),
    output_dir: Path = typer.Option("posts/", "--output", help="Diretório de saída para posts."),
    preview: bool = typer.Option(False, "--preview", help="Serve o site estático após a geração."),
    archive: bool = typer.Option(False, "--archive", help="Arquiva os embeddings no IA."),
) -> None:
    """Executa o pipeline de geração completo."""
    config = PipelineConfig(
        zip_files=[zip_file],
        posts_dir=output_dir,
        rag=RAGConfig(enabled=inject_rag),
    )
    processor = UnifiedProcessor(config)
    processor.process_all()

    builder = StaticSiteBuilder(config)
    builder.build()

    # TODO: Implement preview and archive functionality
    if preview:
        builder.serve()
    if archive:
        archive_app(["upload", "embeddings.parquet"])






# Main app with subcommands
app.add_typer(ingest_app, name="ingest")
app.add_typer(gen_app, name="gen")
app.add_typer(embed_app, name="embed")
app.add_typer(archive_app, name="archive")
app.add_typer(rag_app, name="rag")


@app.command()
def pipeline(
    zip_file: Path = typer.Argument(..., help="Caminho para o arquivo ZIP de entrada."),
    days: int = typer.Option(3, "--days", help="Número de dias para processar."),
    preview: bool = typer.Option(False, "--preview", help="Ativa o preview do site estático."),
    archive: bool = typer.Option(False, "--archive", help="Ativa o arquivamento no IA."),
) -> None:
    """Executa o pipeline completo: ingest -> embed -> rag -> gen -> static -> archive."""
    console.print("🚀 Executing the full pipeline...")

    # Ingest
    ingest_app(["run", str(zip_file), "--output", "ingest.parquet"])

    # Embed
    embed_app(["run", "ingest.parquet", "--output", "embeddings.parquet"])

    # Gen
    gen_app(
        [
            "run",
            str(zip_file),
            "--inject-rag",
            "--output",
            "posts/",
            "--preview" if preview else "--no-preview",
            "--archive" if archive else "--no-archive",
        ]
    )


def run() -> None:
    """Entry point used by the console script."""
    app()


if __name__ == "__main__":
    run()
