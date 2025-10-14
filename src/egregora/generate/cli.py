"""CLI helpers for the generation subsystem."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..archive.uploader import ArchiveManager, ArchiveUploadError
from ..config import PipelineConfig
from ..generate.core import (
    FastMCPContextClient,
    PostContext,
    PostGenerator,
    PromptRenderer,
    RAGClient,
)
from ..models import GroupSource
from ..types import GroupSlug
from ..static.builder import (
    MkDocsExecutionError,
    MkDocsNotInstalledError,
    StaticSiteBuilder,
)


console = Console()
generate_app = typer.Typer(
    help="Gerar conteúdos a partir de datasets Polars já anonimizados",
    invoke_without_command=True,
)


def _run_generation(  # noqa: PLR0913
    dataset: Path,
    *,
    output: Path | None,
    group_name: str | None,
    group_slug: str | None,
    template: Path | None,
    previous_post: Path | None,
    inject_rag: bool,
    rag_endpoint: str | None,
    rag_top_k: int,
    rag_min_similarity: float,
    show_console: bool,
    build_static: Optional[bool],
    preview_site: bool,
    preview_host: Optional[str],
    preview_port: Optional[int],
    archive_dataset: bool,
    archive_identifier: str | None,
    archive_suffix: str | None,
    archive_metadata: dict[str, str],
    dry_run: bool,
    rag_client: RAGClient | None = None,
) -> None:
    frame = _load_frame(dataset)
    if frame.is_empty():
        console.print("⚠️ Dataset vazio; nada para gerar.")
        return

    resolved_group_name = group_name or _unique_string(frame, "group_name") or "Egregora"
    resolved_group_slug = group_slug or _unique_string(frame, "group_slug") or _derive_slug(resolved_group_name)

    config = PipelineConfig(
        posts_dir=output or Path("docs/posts"),
        group_name=resolved_group_name,
        group_slug=GroupSlug(resolved_group_slug),
    )
    # O dataset carregado já passou por anonimização no comando `pipeline`, que
    # aplica `anonymise_frame` e preenche `anon_author` com pseudônimos estáveis.
    # Mantemos essa identidade ao desabilitar a anonimização na etapa de geração
    # para evitar reatribuir pseudônimos inconsistentes nos posts produzidos.
    config.anonymization.enabled = False

    if preview_host is not None:
        config.static_site.preview_host = preview_host
    if preview_port is not None:
        config.static_site.preview_port = preview_port

    use_rag = inject_rag or rag_client is not None

    if use_rag:
        config.rag.enabled = True
        config.rag.top_k = rag_top_k
        config.rag.min_similarity = rag_min_similarity
        if rag_client is None:
            if not rag_endpoint:
                console.print("❌ Para usar --inject-rag informe também --rag-endpoint.")
                raise typer.Exit(1)
            rag_client = FastMCPContextClient(rag_endpoint)
    else:
        config.rag.enabled = False
        rag_client = None

    renderer = PromptRenderer(template_path=template) if template else None
    generator = PostGenerator(config, prompt_renderer=renderer, rag_client=rag_client)
    source = GroupSource(slug=GroupSlug(resolved_group_slug), name=resolved_group_name, exports=[])

    previous_text = previous_post.read_text(encoding="utf-8") if previous_post else None

    output_dir = output or config.posts_dir
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for target_date, day_frame in _group_by_date(frame):
        transcript = _build_transcript(day_frame)
        enrichment = _collect_enrichment(day_frame)
        rag_query = _build_rag_seed(day_frame) if use_rag else None

        context = PostContext(
            group_name=resolved_group_name,
            transcript=transcript,
            target_date=target_date,
            previous_post=previous_text,
            enrichment_section=enrichment,
            rag_query=rag_query,
        )

        rendered = generator.generate(source, context)

        if show_console or dry_run:
            console.print(Panel(rendered, title=f"Prévia {target_date.isoformat()}"))

        if not dry_run:
            filename = f"{target_date.isoformat()}-{resolved_group_slug}.md"
            destination = output_dir / filename
            destination.write_text(rendered, encoding="utf-8")
            rows.append((target_date.isoformat(), str(destination)))

    if dry_run:
        return

    static_builder = StaticSiteBuilder(config)
    static_config = config.static_site
    should_build = static_config.enabled and (
        preview_site
        or (build_static if build_static is not None else static_config.auto_build)
    )

    if should_build:
        try:
            copied = static_builder.sync_posts(output_dir)
            if copied:
                console.print(
                    Panel(
                        f"{len(copied)} arquivos sincronizados com {static_builder.destination_dir}",
                        title="MkDocs",
                    )
                )
            static_builder.build_site()
            console.print("✅ Site estático atualizado com sucesso.")
        except MkDocsNotInstalledError as error:
            console.print(f"⚠️ Prévia MkDocs indisponível: {error}")
            if preview_site:
                raise typer.Exit(1)
        except MkDocsExecutionError as error:
            console.print(f"❌ Falha ao construir site estático: {error}")
            if preview_site:
                raise typer.Exit(1)

    if preview_site:
        try:
            console.print(
                f"🌐 Servindo MkDocs em http://{config.static_site.preview_host}:{config.static_site.preview_port} (Ctrl+C para sair)"
            )
            static_builder.serve_site()
        except MkDocsNotInstalledError as error:
            console.print(f"❌ Não foi possível iniciar a prévia: {error}")
            raise typer.Exit(1)
        except MkDocsExecutionError as error:
            console.print(f"❌ mkdocs serve falhou: {error}")
            raise typer.Exit(1)

    if archive_dataset:
        if dry_run:
            console.print("ℹ️ Dry-run: dataset não será enviado ao Internet Archive.")
        else:
            config.archive.enabled = True
            manager = ArchiveManager(config)
            try:
                result = manager.upload_dataset(
                    dataset,
                    identifier=archive_identifier,
                    suffix=archive_suffix,
                    metadata=archive_metadata,
                    dry_run=False,
                )
            except ArchiveUploadError as error:
                console.print(f"❌ Falha ao arquivar dataset: {error}")
                raise typer.Exit(1) from error
            console.print(
                Panel(
                    f"Dataset arquivado como {result.identifier}.\nCópia local: {result.local_copy}",
                    title="Internet Archive",
                )
            )

    if rows:
        table = Table(title="Posts geradas")
        table.add_column("Data")
        table.add_column("Arquivo")
        for row in rows:
            table.add_row(*row)
        console.print(table)


@generate_app.callback()
def generate_callback(  # noqa: PLR0913
    ctx: typer.Context,
    dataset: Path = typer.Argument(None, help="Arquivo Parquet/CSV com mensagens processadas"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Diretório para salvar as posts"),
    group_name: str | None = typer.Option(None, "--group-name", help="Nome do grupo (opcional)"),
    group_slug: str | None = typer.Option(None, "--group-slug", help="Slug do grupo (opcional)"),
    template: Path | None = typer.Option(None, "--template", help="Modelo Jinja customizado"),
    previous_post: Path | None = typer.Option(None, "--previous-post", help="Post do dia anterior para contexto"),
    inject_rag: bool = typer.Option(False, "--inject-rag/--no-inject-rag", help="Consulta servidor FastMCP"),
    rag_endpoint: str | None = typer.Option(None, "--rag-endpoint", help="Endpoint FastMCP (ex.: http://127.0.0.1:8765/mcp)"),
    rag_top_k: int = typer.Option(3, "--rag-top-k", min=1, help="Quantidade de snippets históricos"),
    rag_min_similarity: float = typer.Option(0.65, "--rag-min-similarity", help="Similaridade mínima (0-1)"),
    show_console: bool = typer.Option(False, "--show", help="Mostra o resultado no terminal"),
    build_static: Optional[bool] = typer.Option(
        None,
        "--build-static/--no-build-static",
        help="Controla se o site estático deve ser reconstruído após a geração",
        show_default=False,
    ),
    preview_site: bool = typer.Option(
        False,
        "--preview",
        "--preview-site",
        help="Inicia mkdocs serve após sincronizar os arquivos",
    ),
    preview_host: Optional[str] = typer.Option(None, "--preview-host", help="Host para mkdocs serve"),
    preview_port: Optional[int] = typer.Option(None, "--preview-port", help="Porta para mkdocs serve"),
    archive_dataset: bool = typer.Option(
        False,
        "--archive/--no-archive",
        help="Envia o dataset de entrada ao Internet Archive após a geração.",
    ),
    archive_identifier: str | None = typer.Option(
        None,
        "--archive-identifier",
        help="Identificador manual para o upload no Internet Archive.",
    ),
    archive_suffix: str | None = typer.Option(
        None,
        "--archive-suffix",
        help="Sufixo adicional quando o identificador for gerado automaticamente.",
    ),
    archive_metadata: list[str] = typer.Option(
        [],
        "--archive-meta",
        help="Metadados extras no formato chave=valor (pode repetir a opção).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Não grava arquivos em disco"),
) -> None:
    if ctx.invoked_subcommand:
        return
    if dataset is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    metadata_payload = _parse_metadata_options(archive_metadata)
    _run_generation(
        dataset,
        output=output,
        group_name=group_name,
        group_slug=group_slug,
        template=template,
        previous_post=previous_post,
        inject_rag=inject_rag,
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
    )


@generate_app.command("render")
def render_command(  # noqa: PLR0913
    dataset: Path = typer.Argument(..., help="Arquivo Parquet/CSV com mensagens processadas"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Diretório para salvar as posts"),
    group_name: str | None = typer.Option(None, "--group-name", help="Nome do grupo (opcional)"),
    group_slug: str | None = typer.Option(None, "--group-slug", help="Slug do grupo (opcional)"),
    template: Path | None = typer.Option(None, "--template", help="Modelo Jinja customizado"),
    previous_post: Path | None = typer.Option(None, "--previous-post", help="Post do dia anterior para contexto"),
    inject_rag: bool = typer.Option(False, "--inject-rag/--no-inject-rag", help="Consulta servidor FastMCP"),
    rag_endpoint: str | None = typer.Option(None, "--rag-endpoint", help="Endpoint FastMCP (ex.: http://127.0.0.1:8765/mcp)"),
    rag_top_k: int = typer.Option(3, "--rag-top-k", min=1, help="Quantidade de snippets históricos"),
    rag_min_similarity: float = typer.Option(0.65, "--rag-min-similarity", help="Similaridade mínima (0-1)"),
    show_console: bool = typer.Option(False, "--show", help="Mostra o resultado no terminal"),
    build_static: Optional[bool] = typer.Option(
        None,
        "--build-static/--no-build-static",
        help="Controla se o site estático deve ser reconstruído após a geração",
        show_default=False,
    ),
    preview_site: bool = typer.Option(
        False,
        "--preview",
        "--preview-site",
        help="Inicia mkdocs serve após sincronizar os arquivos",
    ),
    preview_host: Optional[str] = typer.Option(None, "--preview-host", help="Host para mkdocs serve"),
    preview_port: Optional[int] = typer.Option(None, "--preview-port", help="Porta para mkdocs serve"),
    archive_dataset: bool = typer.Option(
        False,
        "--archive/--no-archive",
        help="Envia o dataset de entrada ao Internet Archive após a geração.",
    ),
    archive_identifier: str | None = typer.Option(
        None,
        "--archive-identifier",
        help="Identificador manual para o upload no Internet Archive.",
    ),
    archive_suffix: str | None = typer.Option(
        None,
        "--archive-suffix",
        help="Sufixo adicional quando o identificador for gerado automaticamente.",
    ),
    archive_metadata: list[str] = typer.Option(
        [],
        "--archive-meta",
        help="Metadados extras no formato chave=valor (pode repetir a opção).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Não grava arquivos em disco"),
) -> None:
    metadata_payload = _parse_metadata_options(archive_metadata)
    _run_generation(
        dataset,
        output=output,
        group_name=group_name,
        group_slug=group_slug,
        template=template,
        previous_post=previous_post,
        inject_rag=inject_rag,
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
    )


def _parse_metadata_options(pairs: Iterable[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(
                "Metadados devem estar no formato chave=valor.", param_name="archive_meta"
            )
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter("Chave de metadado não pode ser vazia.", param_name="archive_meta")
        metadata[key] = value.strip()
    return metadata


def _load_frame(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path)
    if suffix in {".json", ".ndjson"}:
        return pl.read_json(path)
    raise typer.BadParameter(f"Formato de dataset não suportado: {path.suffix}")


def _unique_string(frame: pl.DataFrame, column: str) -> str | None:
    if column not in frame.columns:
        return None
    values = [value for value in frame.get_column(column).to_list() if value]
    return str(values[0]) if values else None


def _derive_slug(name: str) -> str:
    sanitized = "".join(ch if ch.isalnum() else "-" for ch in name.lower())
    collapsed = "-".join(part for part in sanitized.split("-") if part)
    return collapsed or "egregora"


def _group_by_date(frame: pl.DataFrame) -> Iterable[tuple[date, pl.DataFrame]]:
    if "date" not in frame.columns:
        raise typer.BadParameter("Dataset precisa conter coluna 'date'.")
    date_series = frame.get_column("date")
    dates = sorted({entry for entry in date_series.to_list() if entry})
    is_temporal = date_series.dtype in {pl.Date, pl.Datetime}
    for entry in dates:
        if isinstance(entry, date):
            target = entry
        else:
            target = date.fromisoformat(str(entry))
        comparator = target if is_temporal else target.isoformat()
        yield target, frame.filter(pl.col("date") == comparator)


def _build_transcript(frame: pl.DataFrame) -> str:
    time_col = "time" if "time" in frame.columns else None
    author_col = "anon_author" if "anon_author" in frame.columns else "author"

    lines: list[str] = []
    for row in frame.iter_rows(named=True):
        raw_time = row.get(time_col) if time_col else None
        if not raw_time and "timestamp" in row:
            timestamp = row.get("timestamp")
            raw_time = getattr(timestamp, "strftime", lambda *_: None)("%H:%M") if timestamp else None
        time_str = str(raw_time) if raw_time else "--:--"
        author = row.get(author_col) or "Member-XXXX"
        message = row.get("message") or ""
        lines.append(f"{time_str} — {author}: {message}".strip())
    return "\n".join(lines)


def _collect_enrichment(frame: pl.DataFrame) -> str | None:
    if "enriched_summary" not in frame.columns:
        return None
    summaries = [
        str(value).strip()
        for value in frame.get_column("enriched_summary").to_list()
        if value
    ]
    return "\n".join(summaries) if summaries else None


def _build_rag_seed(frame: pl.DataFrame) -> str | None:
    if "message" not in frame.columns:
        return None
    messages = [str(text) for text in frame.get_column("message").to_list() if text]
    if not messages:
        return None
    seed = "\n".join(messages[:20])
    return seed[:2000]


__all__ = ["generate_app", "generate_callback", "render_command"]
