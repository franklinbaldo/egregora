"""Command line interface for the refactored Egregora pipeline."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import polars as pl
import typer
from rich.console import Console

from .archive import archive_app as archive_cli_app
from .config import PipelineConfig
from .embed import register_embed_command
from .generate.cli import _parse_metadata_options, _run_generation, generate_app
from .ingest import ingest_app as ingest_cli_app
from .pipeline_runner import (
    anonymise_frame,
    build_local_rag_client,
    determine_identity,
    embed_dataframe,
    filter_by_window,
    ingest_exports,
    persist_dataframe,
)
from .rag_context import rag_app as rag_cli_app
from .types import GroupSlug

console = Console()
app = typer.Typer(help="Egregora - pipeline local-first de posts com IA")
app.add_typer(generate_app, name="gen")
app.add_typer(ingest_cli_app, name="ingest")
register_embed_command(app)
app.add_typer(rag_cli_app, name="rag")
app.add_typer(archive_cli_app, name="archive")


@app.command("pipeline")
def pipeline_command(  # noqa: PLR0913, PLR0912
    zip_paths: list[Path] = typer.Argument(..., help="Exports do WhatsApp (ZIP) a serem processados"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Diretório onde as posts serão escritas"),
    workspace: Path = typer.Option(Path("tmp-tests/pipeline"), "--workspace", help="Diretório para artefatos intermediários"),
    dataset_out: Path | None = typer.Option(None, "--dataset-out", help="Arquivo Parquet para salvar o dataset consolidado"),
    days: int | None = typer.Option(None, "--days", min=1, help="Limita a N dias mais recentes"),
    from_date: str | None = typer.Option(None, "--from-date", help="Data inicial (YYYY-MM-DD)", formats=["%Y-%m-%d"]),
    to_date: str | None = typer.Option(None, "--to-date", help="Data final (YYYY-MM-DD)", formats=["%Y-%m-%d"]),
    inject_rag: bool = typer.Option(True, "--inject-rag/--no-inject-rag", help="Habilita busca de contexto via RAG local"),
    rag_endpoint: str | None = typer.Option(None, "--rag-endpoint", help="Endpoint FastMCP externo para reutilizar um servidor existente"),
    rag_top_k: int = typer.Option(3, "--rag-top-k", min=1, help="Snippets históricos para cada post"),
    rag_min_similarity: float = typer.Option(0.65, "--rag-min-similarity", help="Similaridade mínima (0-1)"),
    show_console: bool = typer.Option(False, "--show", help="Mostra as posts no terminal após a geração"),
    build_static: bool | None = typer.Option(
        None,
        "--build-static/--no-build-static",
        help="Força reconstrução do site estático após a geração",
        show_default=False,
    ),
    preview_site: bool = typer.Option(False, "--preview", "--preview-site", help="Executa mkdocs serve ao final"),
    preview_host: str | None = typer.Option(None, "--preview-host", help="Host para mkdocs serve"),
    preview_port: int | None = typer.Option(None, "--preview-port", help="Porta para mkdocs serve"),
    archive_dataset: bool = typer.Option(False, "--archive/--no-archive", help="Envia o dataset final ao Internet Archive"),
    archive_identifier: str | None = typer.Option(None, "--archive-identifier", help="Identificador fixo para upload"),
    archive_suffix: str | None = typer.Option(None, "--archive-suffix", help="Sufixo extra para identificadores automáticos"),
    archive_metadata: list[str] = typer.Option([], "--archive-meta", help="Metadados extras chave=valor"),
    keep_intermediate: bool = typer.Option(
        True,
        "--keep-intermediate/--discard-intermediate",
        help="Mantém o dataset Parquet gerado após a execução",
    ),
    template: Path | None = typer.Option(None, "--template", help="Template Jinja customizado"),
    previous_post: Path | None = typer.Option(None, "--previous-post", help="Post anterior para contexto"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Executa sem gravar posts em disco"),
) -> None:
    """Executa ingestão → embeddings → geração em uma única chamada."""

    if not zip_paths:
        console.print("❌ Informe pelo menos um arquivo ZIP do WhatsApp.")
        raise typer.Exit(1)

    try:
        from_date_value = date.fromisoformat(from_date) if from_date else None
    except ValueError as error:
        console.print(f"❌ Data inicial inválida: {error}")
        raise typer.Exit(1) from error

    try:
        to_date_value = date.fromisoformat(to_date) if to_date else None
    except ValueError as error:
        console.print(f"❌ Data final inválida: {error}")
        raise typer.Exit(1) from error

    metadata_payload = _parse_metadata_options(archive_metadata)

    config = PipelineConfig(posts_dir=output or Path("docs/posts"))

    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    console.print("📥 Ingerindo exports...")
    frame = ingest_exports(zip_paths)
    if frame.is_empty():
        console.print("❌ Nenhuma mensagem encontrada nos arquivos fornecidos.")
        raise typer.Exit(1)

    frame = anonymise_frame(frame, config)
    frame = filter_by_window(frame, days=days, start=from_date_value, end=to_date_value)
    if frame.is_empty():
        console.print("⚠️ Nenhuma mensagem restante após aplicar os filtros de data.")
        raise typer.Exit(0)

    group_name, group_slug = determine_identity(frame, config)
    config.group_name = group_name
    config.group_slug = GroupSlug(group_slug)

    frame = frame.with_columns(
        pl.lit(group_name).alias("group_name"),
        pl.lit(group_slug).alias("group_slug"),
    )

    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    dataset_path = dataset_out or workspace / f"{group_slug}-{run_id}.parquet"

    console.print("🧮 Gerando embeddings com Gemini...")
    try:
        embedded_frame, embedder = embed_dataframe(frame, config)
    except RuntimeError as error:
        console.print(f"❌ Falha ao gerar embeddings: {error}")
        raise typer.Exit(1) from error

    dataset_path = persist_dataframe(embedded_frame, dataset_path)
    console.print(f"💾 Dataset consolidado em {dataset_path}")

    rag_enabled = inject_rag or bool(rag_endpoint)
    rag_client = None
    if rag_enabled and not rag_endpoint:
        console.print("🧠 Construindo índice DuckDB em memória...")
        try:
            rag_client = build_local_rag_client(dataset_path, config=config, embedder=embedder)
        except Exception as error:  # pragma: no cover - duckdb/vss setup errors
            console.print(f"⚠️ Não foi possível inicializar o RAG local: {error}")
            rag_enabled = False
            rag_client = None

    console.print("📝 Gerando posts...")
    _run_generation(
        dataset_path,
        output=output,
        group_name=group_name,
        group_slug=group_slug,
        template=template,
        previous_post=previous_post,
        inject_rag=rag_enabled,
        rag_endpoint=rag_endpoint,
        rag_top_k=rag_top_k,
        rag_min_similarity=rag_min_similarity,
        show_console=show_console,
        build_static=build_static,
        preview_site=preview_site,
        preview_host=preview_host,
        preview_port=preview_port,
        archive_dataset=archive_dataset,
        archive_identifier=archive_identifier,
        archive_suffix=archive_suffix,
        archive_metadata=metadata_payload,
        dry_run=dry_run,
        rag_client=rag_client,
    )

    if not keep_intermediate and not dry_run and dataset_out is None:
        dataset_path.unlink(missing_ok=True)
        console.print("🧹 Artefatos intermediários removidos.")


def run() -> None:
    """Entry point used by the console script."""

    app()


if __name__ == "__main__":
    run()
