"""Typer application for generating embeddings from data frames."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import typer
from rich.console import Console

from .embed import EmbeddingResult, GeminiEmbedder

console = Console()
embed_app = typer.Typer(
    help="Gere embeddings Gemini para DataFrames normalizados pela etapa de ingestão.",
    add_completion=False,
)


def run_embeddings(  # noqa: PLR0913
    dataframe_path: Path = typer.Argument(
        ..., exists=True, readable=True, help="Arquivo produzido pela etapa de ingestão (Parquet/CSV/JSON)."
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Arquivo Parquet para salvar o resultado (padrão: <input>_embeddings.parquet)",
    ),
    text_column: str = typer.Option("message", "--text-column", help="Coluna com o texto original."),
    vector_column: str = typer.Option("vector", "--vector-column", help="Coluna onde o embedding será salvo."),
    model: str = typer.Option("models/embedding-001", "--model", help="Modelo Gemini a ser utilizado."),
    batch_size: int = typer.Option(10, "--batch-size", min=1, help="Número de mensagens processadas por lote."),
    chunk_char_limit: int = typer.Option(
        2048, "--chunk-char-limit", min=1, help="Tamanho máximo de caracteres por chamada ao Gemini."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Apenas mostra as configurações sem gerar embeddings."),
) -> EmbeddingResult:
    frame = _load_frame(dataframe_path)
    if dry_run:
        console.print(
            f"ℹ️ Execução em modo dry-run para {dataframe_path}. "
            f"Linhas detectadas: {frame.height}. Model: {model}."
        )
        return EmbeddingResult(
            total_texts=frame.height,
            model=model,
            vector_column=vector_column,
            text_column=text_column,
        )

    embedder = GeminiEmbedder(
        model=model,
        batch_size=batch_size,
        max_input_chars=chunk_char_limit,
    )

    embedded = embedder.embed_dataframe(frame, text_column=text_column, vector_column=vector_column)
    destination = _resolve_output_path(dataframe_path, output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    embedded.write_parquet(destination)
    console.print(
        f"✅ Embeddings salvos em {destination} ({embedded.height} linhas, coluna '{vector_column}')."
    )
    return EmbeddingResult(
        total_texts=embedded.height,
        model=model,
        vector_column=vector_column,
        text_column=text_column,
    )


@embed_app.command("run")
def embed_command(
    dataframe_path: Path = typer.Argument(
        ..., exists=True, readable=True, help="Arquivo produzido pela etapa de ingestão (Parquet/CSV/JSON)."
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Arquivo Parquet para salvar o resultado (padrão: <input>_embeddings.parquet)",
    ),
    text_column: str = typer.Option("message", "--text-column", help="Coluna com o texto original."),
    vector_column: str = typer.Option("vector", "--vector-column", help="Coluna onde o embedding será salvo."),
    model: str = typer.Option("models/embedding-001", "--model", help="Modelo Gemini a ser utilizado."),
    batch_size: int = typer.Option(10, "--batch-size", min=1, help="Número de mensagens processadas por lote."),
    chunk_char_limit: int = typer.Option(
        2048, "--chunk-char-limit", min=1, help="Tamanho máximo de caracteres por chamada ao Gemini."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Apenas mostra as configurações sem gerar embeddings."),
) -> EmbeddingResult:
    """Expose ``run_embeddings`` as ``egregora embed run`` for debugging."""

    return run_embeddings(
        dataframe_path=dataframe_path,
        output=output,
        text_column=text_column,
        vector_column=vector_column,
        model=model,
        batch_size=batch_size,
        chunk_char_limit=chunk_char_limit,
        dry_run=dry_run,
    )


def register_embed_command(app: typer.Typer) -> None:
    """Register ``egregora embed`` directly on the main Typer application."""

    app.command("embed")(run_embeddings)


def _load_frame(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path)
    if suffix in {".json", ".ndjson"}:
        return pl.read_json(path, infer_schema_length=None)
    raise typer.BadParameter(
        "Formato não suportado para embeddings. Use Parquet, CSV ou JSON.",
        param_name="dataframe_path",
    )


def _resolve_output_path(source: Path, output: Path | None) -> Path:
    if output:
        return output
    return source.with_name(f"{source.stem}_embeddings.parquet")


__all__ = ["embed_app", "run_embeddings", "register_embed_command"]
