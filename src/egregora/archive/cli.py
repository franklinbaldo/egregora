"""Typer commands for Internet Archive uploads/downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import typer
from rich.console import Console

from ..config import PipelineConfig
from .uploader import (
    ArchiveDownloadError,
    ArchiveDownloadResult,
    ArchiveManager,
    ArchiveNotFoundError,
    ArchiveUploadError,
    ArchiveUploadResult,
)

console = Console()
archive_app = typer.Typer(
    help="Gerencie exportações do Internet Archive para datasets do Egregora.",
    add_completion=False,
)


def _initialise_config(dataset_dir: Path | None = None) -> PipelineConfig:
    config = PipelineConfig()
    if dataset_dir is not None:
        config.archive.dataset_dir = dataset_dir
    return config


def _parse_metadata(pairs: Iterable[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(
                "Metadados devem seguir o formato chave=valor (ex.: --meta projeto=egregora).",
                param_name="metadata",
            )
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter("Chave de metadado não pode ser vazia.", param_name="metadata")
        metadata[key] = value.strip()
    return metadata


@archive_app.command("upload")
def upload_command(  # noqa: PLR0913
    parquet_path: Path = typer.Argument(
        ..., exists=True, readable=True, dir_okay=False, help="Arquivo Parquet com embeddings gerados.",
    ),
    identifier: str | None = typer.Option(
        None,
        "--identifier",
        "-i",
        help="Identificador completo para o item no Internet Archive (padrão: prefixo configurado + data).",
    ),
    suffix: str | None = typer.Option(
        None,
        "--suffix",
        help="Sufixo adicional para compor o identificador (ex.: run-001). Ignorado se --identifier for usado.",
    ),
    metadata: list[str] = typer.Option(
        [],
        "--meta",
        help="Metadados extras no formato chave=valor. Pode ser informado múltiplas vezes.",
    ),
    dataset_dir: Path | None = typer.Option(
        None,
        "--dataset-dir",
        help="Diretório local para guardar a cópia enviada (padrão: data/exports).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Não envia nada, apenas relata a operação."),
) -> ArchiveUploadResult:
    config = _initialise_config(dataset_dir)
    if not dry_run:
        config.archive.enabled = True

    manager = ArchiveManager(config)
    metadata_payload = _parse_metadata(metadata)

    try:
        result = manager.upload_dataset(
            parquet_path,
            identifier=identifier,
            suffix=suffix,
            metadata=metadata_payload,
            dry_run=dry_run,
        )
    except ArchiveUploadError as error:
        console.print(f"❌ Falha ao enviar dataset: {error}")
        raise typer.Exit(1) from error

    if dry_run:
        console.print(
            f"ℹ️ Dry-run: dataset seria arquivado como {result.identifier} com metadados {result.metadata}."
        )
    else:
        console.print(
            f"☁️ Dataset '{result.source.name}' arquivado como {result.identifier}. "
            f"Cópia local: {result.local_copy}."
        )
    return result


@archive_app.command("download")
def download_command(  # noqa: PLR0913
    identifier: str | None = typer.Option(
        None,
        "--identifier",
        "-i",
        help="Identificador completo do item a baixar.",
    ),
    latest: bool = typer.Option(
        False,
        "--latest",
        help="Baixa automaticamente o item mais recente com o prefixo configurado.",
    ),
    destination: Path | None = typer.Option(
        None,
        "--destination",
        "-d",
        help="Diretório onde os arquivos serão salvos (padrão: data/exports).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula o download sem acessar a Internet."),
) -> ArchiveDownloadResult:
    if not identifier and not latest:
        raise typer.BadParameter("Informe --identifier ou --latest para continuar.")

    config = _initialise_config(destination)
    manager = ArchiveManager(config)

    try:
        if latest:
            result = manager.download_latest(destination=destination, dry_run=dry_run)
        else:
            result = manager.download_identifier(identifier or "", destination=destination, dry_run=dry_run)
    except ArchiveNotFoundError as error:
        console.print(f"⚠️ {error}")
        raise typer.Exit(1) from error
    except ArchiveDownloadError as error:
        console.print(f"❌ Falha ao baixar dataset: {error}")
        raise typer.Exit(1) from error

    if dry_run:
        console.print(
            f"ℹ️ Dry-run: item {result.identifier} seria baixado para {result.destination}."
        )
    else:
        files = ", ".join(path.name for path in result.files) if result.files else "sem arquivos detectados"
        console.print(
            f"⬇️ Dataset {result.identifier} baixado para {result.destination}. Arquivos: {files}."
        )
    return result


__all__ = ["archive_app", "download_command", "upload_command"]
