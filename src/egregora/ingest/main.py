"""Typer entrypoint for the ingestion helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import typer
from rich.console import Console
from rich.table import Table

from .parser import parse_zip

console = Console()
ingest_app = typer.Typer(help="Polars/Ibis ingestion building blocks for the refactor")


def ingest_zip(
    zip_path: Path,
    *,
    chat_filename: str | None = None,
    group_name: str | None = None,
    group_slug: str | None = None,
    export_date: date | None = None,
) -> pl.DataFrame:
    """Return a parsed Polars DataFrame for ``zip_path`` ready for anonymization."""

    return parse_zip(
        zip_path,
        chat_filename=chat_filename,
        group_name=group_name,
        group_slug=group_slug,
        export_date=export_date,
    )


@ingest_app.command("zip")
def ingest_zip_command(  # noqa: PLR0913
    zip_path: Path = typer.Argument(..., help="ZIP export gerado pelo WhatsApp"),
    chat_filename: str | None = typer.Option(
        None,
        "--chat-file",
        help="Nome exato do arquivo de conversa dentro do ZIP (auto-detectado se vazio)",
    ),
    group_name: str | None = typer.Option(
        None,
        "--group-name",
        help="Nome do grupo para sobrescrever a detecção automática",
    ),
    group_slug: str | None = typer.Option(
        None,
        "--group-slug",
        help="Slug do grupo para sobrescrever a geração automática",
    ),
    export_date: str | None = typer.Option(
        None,
        "--export-date",
        help="Data de referência do export (YYYY-MM-DD)",
        formats=["%Y-%m-%d"],
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Arquivo opcional para salvar o resultado (inferimos o formato pelo sufixo)",
    ),
    preview_rows: int = typer.Option(5, "--preview-rows", help="Número de linhas para mostrar na prévia"),
) -> None:
    """Parseia o ZIP e mostra/gera o DataFrame resultante."""

    try:
        parsed_export = date.fromisoformat(export_date) if export_date else None
    except ValueError as error:
        console.print(f"❌ Data de export inválida: {error}")
        raise typer.Exit(1) from error

    frame = ingest_zip(
        zip_path,
        chat_filename=chat_filename,
        group_name=group_name,
        group_slug=group_slug,
        export_date=parsed_export,
    )

    if output:
        _write_output(frame, output)
    else:
        _render_preview(frame, preview_rows)


def _render_preview(frame: pl.DataFrame, preview_rows: int) -> None:
    if frame.is_empty():
        console.print("⚠️ Nenhuma mensagem encontrada neste export.")
        return

    head = frame.select(
        "timestamp",
        "author",
        "anon_author",
        "message",
        "enriched_summary",
    ).head(preview_rows)

    table = Table(title="Prévia do DataFrame", show_header=True, header_style="bold cyan")
    for column in head.columns:
        table.add_column(column)

    for row in head.iter_rows():
        formatted = [
            str(value) if value is not None else "—"
            for value in row
        ]
        table.add_row(*formatted)

    console.print(table)
    console.print(f"Total de linhas: {frame.height}")


def _write_output(frame: pl.DataFrame, output: Path) -> None:
    suffix = output.suffix.lower()
    if suffix == ".parquet":
        frame.write_parquet(output)
        console.print(f"💾 DataFrame salvo em Parquet: {output}")
    elif suffix == ".csv":
        frame.write_csv(output)
        console.print(f"💾 DataFrame salvo em CSV: {output}")
    elif suffix in {".json", ".ndjson"}:
        frame.write_json(output, row_oriented=True)
        console.print(f"💾 DataFrame salvo em JSON orientado a linhas: {output}")
    else:
        frame.write_csv(output.with_suffix(".csv"))
        console.print(
            "Formato não reconhecido; salvamos como CSV em "
            f"{output.with_suffix('.csv')}"
        )


__all__ = ["ingest_app", "ingest_zip"]
