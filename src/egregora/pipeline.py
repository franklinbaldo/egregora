"""Ultra-simple pipeline: parse → anonymize → group → enrich → write."""

from __future__ import annotations

import importlib
import logging
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    MutableMapping,
    Protocol,
    Sequence,
    Literal,
    TypeAlias,
    TypedDict,
    cast,
)
from zoneinfo import ZoneInfo

# -- Third-party modules ---------------------------------------------------
#
# These imports are performed dynamically so that mypy does not require stub
# packages for ``duckdb``/``ibis``/``google``.  The resulting module objects are
# re-exported with precise ``ModuleType`` annotations so other modules can rely
# on their availability without triggering ``Any`` inference.

duckdb: ModuleType = importlib.import_module("duckdb")
ibis: ModuleType = importlib.import_module("ibis")
google: ModuleType = importlib.import_module("google")
genai = cast("_GenAIModule", importlib.import_module("google.genai"))

__all__ = [
    "duckdb",
    "ibis",
    "google",
    "genai",
    "discover_chat_file",
    "group_by_period",
    "period_has_posts",
    "process_whatsapp_export",
]


class _GenAIClientProtocol(Protocol):
    """Minimal protocol describing the subset used in this module."""

    def close(self) -> None: ...


class _GenAIModule(Protocol):
    """Protocol representing ``google.genai`` used in the pipeline."""

    def Client(self, *, api_key: str | None) -> _GenAIClientProtocol: ...


if TYPE_CHECKING:  # pragma: no cover - only used for type checking
    class Table(Protocol):
        """Shallow protocol for ibis table operations used in this module."""

        def count(self) -> Any: ...

        def mutate(self, **updates: Any) -> Table: ...

        def select(self, *columns: Any) -> Table: ...

        def distinct(self) -> Table: ...

        def execute(self) -> Any: ...

        def filter(self, predicate: Any) -> Table: ...

        def drop(self, *columns: str) -> Table: ...

        def schema(self) -> Any: ...

        @property
        def timestamp(self) -> Any: ...

        def __getattr__(self, item: str) -> Any: ...

else:  # pragma: no cover - runtime protocol fallback
    class Table:  # noqa: D401
        """Runtime placeholder used only for type annotations."""

        pass

logger = logging.getLogger(__name__)

SINGLE_DIGIT_THRESHOLD = 10


StepStatus: TypeAlias = Literal["pending", "in_progress", "completed"]
StepName: TypeAlias = Literal["enrichment", "writing", "profiles", "rag"]


class CheckpointRecord(TypedDict, total=False):
    """Typed representation of checkpoint JSON persisted by ``CheckpointStore``."""

    period: str
    steps: MutableMapping[StepName, StepStatus]
    timestamp: str | None


class PeriodArtifacts(TypedDict, total=False):
    """Artifacts generated for a given period."""

    posts: list[str]
    profiles: list[str]


class EnrichmentCacheProtocol(Protocol):
    def close(self) -> None: ...


class CheckpointStoreProtocol(Protocol):
    def load(self, period: str) -> MutableMapping[str, Any]: ...

    def update_step(self, period: str, step: str, status: str) -> MutableMapping[str, Any]: ...


class GeminiBatchClientProtocol(Protocol):
    @property
    def default_model(self) -> str: ...


class ModelConfigProtocol(Protocol):
    embedding_output_dimensionality: int

    def get_model(self, name: str) -> str: ...


class SitePathsProtocol(Protocol):
    site_root: Path
    docs_dir: Path
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path
    enriched_dir: Path
    rag_dir: Path
    mkdocs_path: Path | None


VectorStoreProtocol = Any
WhatsAppExportFactory = Callable[..., Any]
GroupSlugFactory = Callable[[str], str]

EnrichDataFrameFunc = Callable[..., Table]
ExtractAndReplaceMediaFunc = Callable[..., tuple[Table, dict[str, Path]]]
ParseExportFunc = Callable[..., Table]
ExtractCommandsFunc = Callable[[Table], Sequence[Any]]
ProcessCommandsFunc = Callable[[Iterable[Any], Path], None]
FilterMessagesFunc = Callable[[Table], tuple[Table, int]]
FilterOptedOutFunc = Callable[[Table, Path], tuple[Table, int]]
WritePostsForPeriodFunc = Callable[..., dict[str, list[str]]]
ResolveSitePathsFunc = Callable[[Path], SitePathsProtocol]
IndexAllMediaFunc = Callable[..., int]

EnrichmentCacheFactory = Callable[..., EnrichmentCacheProtocol]
CheckpointStoreFactory = Callable[..., CheckpointStoreProtocol]
GeminiBatchClientFactory = Callable[..., GeminiBatchClientProtocol]
ModelConfigFactory = Callable[..., ModelConfigProtocol]
VectorStoreFactory = Callable[..., VectorStoreProtocol]


@dataclass(slots=True, frozen=True)
class PipelineConfig:
    """Immutable configuration captured at pipeline invocation time."""

    zip_path: Path
    output_dir: Path
    site_paths: SitePathsProtocol
    period: str
    enable_enrichment: bool
    from_date: date | None
    to_date: date | None
    timezone: ZoneInfo | None
    gemini_api_key: str | None
    model: str | None
    resume: bool
    retrieval_mode: str
    retrieval_nprobe: int | None
    retrieval_overfetch: int | None


@dataclass(slots=True)
class RuntimeResources:
    """Mutable runtime state shared across pipeline stages."""

    client: _GenAIClientProtocol | None
    text_batch_client: "GeminiBatchClientProtocol"
    vision_batch_client: "GeminiBatchClientProtocol"
    embedding_batch_client: "GeminiBatchClientProtocol"
    embedding_dimensionality: int
    enrichment_cache: "EnrichmentCacheProtocol"
    checkpoint_store: "CheckpointStoreProtocol"


def _get_step_state(record: CheckpointRecord) -> MutableMapping[StepName, StepStatus]:
    """Return the mutable per-step state from a checkpoint record."""

    steps = record.get("steps")
    if steps is None:
        steps = cast(MutableMapping[StepName, StepStatus], {})
        record["steps"] = steps
    return steps


def _update_checkpoint_state(
    resources: RuntimeResources,
    period_key: str,
    step: StepName,
    status: StepStatus,
) -> MutableMapping[StepName, StepStatus]:
    """Persist an updated step status and return the latest state mapping."""

    record = cast(
        CheckpointRecord,
        resources.checkpoint_store.update_step(period_key, step, status),
    )
    return _get_step_state(record)


def _load_checkpoint(resources: RuntimeResources, period_key: str) -> CheckpointRecord:
    """Load a checkpoint record for ``period_key`` and coerce its typing."""

    return cast(CheckpointRecord, resources.checkpoint_store.load(period_key))


_cache_module = importlib.import_module(".cache", __package__)
EnrichmentCache = cast(EnrichmentCacheFactory, getattr(_cache_module, "EnrichmentCache"))

_checkpoints_module = importlib.import_module(".checkpoints", __package__)
CheckpointStore = cast(
    CheckpointStoreFactory, getattr(_checkpoints_module, "CheckpointStore")
)

_enricher_module = importlib.import_module(".enricher", __package__)
enrich_dataframe = cast(EnrichDataFrameFunc, getattr(_enricher_module, "enrich_dataframe"))
extract_and_replace_media = cast(
    ExtractAndReplaceMediaFunc, getattr(_enricher_module, "extract_and_replace_media")
)

_gemini_batch_module = importlib.import_module(".gemini_batch", __package__)
GeminiBatchClient = cast(
    GeminiBatchClientFactory, getattr(_gemini_batch_module, "GeminiBatchClient")
)

_model_config_module = importlib.import_module(".model_config", __package__)
ModelConfig = cast(ModelConfigFactory, getattr(_model_config_module, "ModelConfig"))
load_site_config = cast(Callable[[Path], Any], getattr(_model_config_module, "load_site_config"))

_models_module = importlib.import_module(".models", __package__)
WhatsAppExport = cast(WhatsAppExportFactory, getattr(_models_module, "WhatsAppExport"))

_parser_module = importlib.import_module(".parser", __package__)
extract_commands = cast(ExtractCommandsFunc, getattr(_parser_module, "extract_commands"))
filter_egregora_messages = cast(
    FilterMessagesFunc, getattr(_parser_module, "filter_egregora_messages")
)
parse_export = cast(ParseExportFunc, getattr(_parser_module, "parse_export"))

_profiler_module = importlib.import_module(".profiler", __package__)
filter_opted_out_authors = cast(
    FilterOptedOutFunc, getattr(_profiler_module, "filter_opted_out_authors")
)
process_commands = cast(ProcessCommandsFunc, getattr(_profiler_module, "process_commands"))

_rag_module = importlib.import_module(".rag", __package__)
VectorStore = cast(VectorStoreFactory, getattr(_rag_module, "VectorStore"))
index_all_media = cast(IndexAllMediaFunc, getattr(_rag_module, "index_all_media"))

_site_config_module = importlib.import_module(".site_config", __package__)
resolve_site_paths = cast(ResolveSitePathsFunc, getattr(_site_config_module, "resolve_site_paths"))

_types_module = importlib.import_module(".types", __package__)
GroupSlug = cast(GroupSlugFactory, getattr(_types_module, "GroupSlug"))

_writer_module = importlib.import_module(".writer", __package__)
write_posts_for_period = cast(
    WritePostsForPeriodFunc, getattr(_writer_module, "write_posts_for_period")
)


def _merge_into_target(source: Path, destination: Path) -> bool:
    """Recursively merge ``source`` contents into ``destination`` directory."""

    moved_any = False

    for item in source.iterdir():
        target_path = destination / item.name

        if item.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            moved_any = _merge_into_target(item, target_path) or moved_any
            if not any(item.iterdir()):
                item.rmdir()
            continue

        if not target_path.exists():
            shutil.move(str(item), str(target_path))
            moved_any = True

    return moved_any


def _migrate_directory(source: Path, target: Path, label: str) -> None:
    """Move legacy content directory into the current docs tree."""

    try:
        source_resolved = source.resolve()
        target_resolved = target.resolve()
    except FileNotFoundError:
        return

    if source_resolved == target_resolved or not source_resolved.exists():
        return

    try:
        items = list(source_resolved.iterdir())
    except (FileNotFoundError, NotADirectoryError):
        return

    if not items:
        return

    target_resolved.mkdir(parents=True, exist_ok=True)

    moved_any = _merge_into_target(source_resolved, target_resolved)

    if not moved_any:
        return

    # Clean up empty legacy directory (ignore errors when residual files remain)
    try:
        source_resolved.rmdir()
    except OSError:
        pass

    logger.info(
        "Migrated %s directory from %s to %s",
        label,
        source_resolved,
        target_resolved,
    )


def _migrate_legacy_structure(site_paths: SitePathsProtocol) -> None:
    """Normalize legacy site structure generated by older scaffold versions."""

    legacy_posts = site_paths.site_root / "posts"
    legacy_profiles = site_paths.site_root / "profiles"
    legacy_media = site_paths.site_root / "media"

    _migrate_directory(legacy_posts, site_paths.posts_dir, "posts")
    _migrate_directory(legacy_profiles, site_paths.profiles_dir, "profiles")
    _migrate_directory(legacy_media, site_paths.media_dir, "media")


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in the ZIP and extract group name."""

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith(".txt") and not member.startswith("__"):
                # Generic pattern to capture group name from WhatsApp chat files
                pattern = r"WhatsApp(?: Chat with|.*) (.+)\.txt"
                match = re.match(pattern, Path(member).name)
                if match:
                    return match.group(1), member
                return Path(member).stem, member

    raise ValueError(f"No WhatsApp chat file found in {zip_path}")


def period_has_posts(period_key: str, posts_dir: Path) -> bool:
    """Check if posts already exist for this period."""
    if not posts_dir.exists():
        return False

    # Look for files matching {period_key}-*.md
    pattern = f"{period_key}-*.md"
    existing_posts = list(posts_dir.glob(pattern))

    return len(existing_posts) > 0


def group_by_period(df: Table, period: str = "day") -> dict[str, Table]:
    """
    Group Table by time period.

    Args:
        df: Table with timestamp column
        period: "day", "week", or "month"

    Returns:
        Dict mapping period string to Table
    """
    if df.count().execute() == 0:
        return {}

    if period == "day":
        df = df.mutate(period=df.timestamp.date().cast("string"))
    elif period == "week":
        # ISO week format: YYYY-Wnn
        year_str = df.timestamp.year().cast("string")
        week_num = df.timestamp.week_of_year()
        week_str = ibis.ifelse(
            week_num < SINGLE_DIGIT_THRESHOLD,
            ibis.literal("0") + week_num.cast("string"),
            week_num.cast("string"),
        )
        df = df.mutate(period=year_str + ibis.literal("-W") + week_str)
    elif period == "month":
        # Format: YYYY-MM
        year_str = df.timestamp.year().cast("string")
        month_num = df.timestamp.month()
        # Zero-pad month: use lpad to ensure 2 digits
        month_str = ibis.ifelse(
            month_num < SINGLE_DIGIT_THRESHOLD,
            ibis.literal("0") + month_num.cast("string"),
            month_num.cast("string"),
        )
        df = df.mutate(period=year_str + ibis.literal("-") + month_str)
    else:
        raise ValueError(f"Unknown period: {period}")

    grouped = {}
    # Get unique period values, sorted
    period_values = sorted(df.select("period").distinct().execute()["period"].tolist())

    for period_value in period_values:
        period_df = df.filter(df.period == period_value).drop("period")
        grouped[period_value] = period_df

    return grouped


def _process_whatsapp_export(  # noqa: PLR0912, PLR0913, PLR0915
    zip_path: Path,
    output_dir: Path,
    *,
    site_paths: SitePathsProtocol,
    period: str = "day",
    enable_enrichment: bool = True,
    from_date: date | None = None,
    to_date: date | None = None,
    timezone: ZoneInfo | None = None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> dict[str, PeriodArtifacts]:
    """
    Complete pipeline: ZIP → posts + profiles.

    Args:
        zip_path: WhatsApp export ZIP file
        output_dir: Where to save posts and profiles
        period: "day", "week", or "month"
        enable_enrichment: Add URL/media context
        from_date: Only process messages from this date onwards (date object)
        to_date: Only process messages up to this date (date object)
        timezone: ZoneInfo timezone object (WhatsApp export phone timezone)
        gemini_api_key: Google Gemini API key
        model: Gemini model to use (overrides mkdocs.yml config)

    Returns:
        Dict mapping period to {'posts': [...], 'profiles': [...]}
    """

    config = PipelineConfig(
        zip_path=zip_path,
        output_dir=output_dir,
        site_paths=site_paths,
        period=period,
        enable_enrichment=enable_enrichment,
        from_date=from_date,
        to_date=to_date,
        timezone=timezone,
        gemini_api_key=gemini_api_key,
        model=model,
        resume=resume,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
    )

    def _load_enriched_table(path: Path, schema: Any) -> Table:
        if not path.exists():
            raise FileNotFoundError(path)
        return ibis.read_csv(str(path), table_schema=schema)

    # Validate MkDocs scaffold exists before proceeding
    if not site_paths.mkdocs_path or not site_paths.mkdocs_path.exists():
        raise ValueError(
            f"No mkdocs.yml found for site at {config.output_dir}. "
            "Run 'egregora init <site-dir>' before processing exports."
        )

    if not site_paths.docs_dir.exists():
        raise ValueError(
            f"Docs directory not found: {site_paths.docs_dir}. "
            "Re-run 'egregora init' to scaffold the MkDocs project."
        )

    # Move legacy structures (from older scaffolds) into docs_dir if needed
    _migrate_legacy_structure(site_paths)

    # Load site config and create model config
    site_config = load_site_config(site_paths.site_root)
    model_config = ModelConfig(cli_model=config.model, site_config=site_config)

    client: _GenAIClientProtocol | None = None
    resources: RuntimeResources | None = None
    try:
        client = genai.Client(api_key=config.gemini_api_key)
        resources = RuntimeResources(
            client=client,
            text_batch_client=GeminiBatchClient(client, model_config.get_model("enricher")),
            vision_batch_client=GeminiBatchClient(client, model_config.get_model("enricher_vision")),
            embedding_batch_client=GeminiBatchClient(
                client, model_config.get_model("embedding")
            ),
            embedding_dimensionality=model_config.embedding_output_dimensionality,
            enrichment_cache=EnrichmentCache(Path(".egregora-cache") / site_paths.site_root.name),
            checkpoint_store=CheckpointStore(site_paths.site_root / ".egregora" / "checkpoints"),
        )

        logger.info(f"[bold cyan]📦 Parsing export:[/] {zip_path}")
        group_name, chat_file = discover_chat_file(zip_path)
        group_slug = GroupSlug(group_name.lower().replace(" ", "-"))
        logger.info(f"[yellow]👥 Discovered chat[/]: {group_name} [dim](source: {chat_file})[/]")

        export = WhatsAppExport(
            zip_path=zip_path,
            group_name=group_name,
            group_slug=group_slug,
            export_date=datetime.now().date(),
            chat_file=chat_file,
            media_files=[],
        )

        # Parse and anonymize (with timezone from phone)
        df = parse_export(export, timezone=config.timezone)
        total_messages = df.count().execute()
        logger.info(f"[green]✅ Loaded[/] {total_messages} messages after parsing")

        # Ensure key directories exist and live inside docs/
        content_dirs = {
            "posts": site_paths.posts_dir,
            "profiles": site_paths.profiles_dir,
            "media": site_paths.media_dir,
        }
        for label, directory in content_dirs.items():
            try:
                directory.relative_to(site_paths.docs_dir)
            except ValueError as exc:
                raise ValueError(
                    f"{label.capitalize()} directory must reside inside the MkDocs docs_dir. "
                    f"Expected parent {site_paths.docs_dir}, got {directory}."
                ) from exc
            directory.mkdir(parents=True, exist_ok=True)

        # Extract and process egregora commands (before filtering)
        commands = extract_commands(df)
        if commands:
            process_commands(commands, site_paths.profiles_dir)
            logger.info(f"[magenta]🧾 Processed[/] {len(commands)} /egregora commands")
        else:
            logger.info("[magenta]🧾 No /egregora commands detected in this export[/]")

        # Remove ALL /egregora messages (commands + ad-hoc exclusions)
        df, egregora_removed = filter_egregora_messages(df)
        if egregora_removed:
            logger.info(f"[yellow]🧹 Removed[/] {egregora_removed} /egregora messages")

        # Filter out opted-out authors EARLY (before any processing)
        df, removed_count = filter_opted_out_authors(df, site_paths.profiles_dir)
        if removed_count > 0:
            logger.warning(f"⚠️  {removed_count} messages removed from opted-out users")

        # Filter by date range if specified
        if config.from_date or config.to_date:
            original_count = df.count().execute()

            if config.from_date and config.to_date:
                df = df.filter(
                    (df.timestamp.date() >= config.from_date)
                    & (df.timestamp.date() <= config.to_date)
                )
                logger.info(
                    f"📅 [cyan]Filtering[/] messages from {config.from_date} to {config.to_date}"
                )
            elif config.from_date:
                df = df.filter(df.timestamp.date() >= config.from_date)
                logger.info(f"📅 [cyan]Filtering[/] messages from {config.from_date} onwards")
            elif config.to_date:
                df = df.filter(df.timestamp.date() <= config.to_date)
                logger.info(f"📅 [cyan]Filtering[/] messages up to {config.to_date}")

            filtered_count = df.count().execute()
            removed_by_date = original_count - filtered_count

            if removed_by_date > 0:
                logger.info(
                    f"🗓️  [yellow]Filtered out[/] {removed_by_date} messages by date (kept {filtered_count})"
                )
            else:
                logger.info(
                    f"[green]✓ All[/] {filtered_count} messages are within the specified date range"
                )

        # Group by period first (media extraction handled per-period)
        logger.info(f"🎯 [bold cyan]Grouping messages by period[/]: {config.period}")
        periods = group_by_period(df, config.period)
        if not periods:
            logger.info("[yellow]No periods found after grouping[/]")
            return {}

        results: dict[str, PeriodArtifacts] = {}
        posts_dir = site_paths.posts_dir
        profiles_dir = site_paths.profiles_dir
        site_paths.enriched_dir.mkdir(parents=True, exist_ok=True)

        for period_key in sorted(periods.keys()):
            period_df = periods[period_key]
            period_count = period_df.count().execute()
            logger.info(f"➡️  [bold]{period_key}[/] — {period_count} messages")

            checkpoint_data = (
                _load_checkpoint(resources, period_key)
                if config.resume
                else cast(CheckpointRecord, {"period": period_key, "steps": {}})
            )
            steps_state = _get_step_state(checkpoint_data)

            period_df, media_mapping = extract_and_replace_media(
                period_df,
                zip_path,
                site_paths.docs_dir,
                posts_dir,
                str(group_slug),
            )

            logger.info(f"Processing {period_key}...")

            enriched_path = site_paths.enriched_dir / f"{period_key}-enriched.csv"

            if config.enable_enrichment:
                logger.info(f"✨ [cyan]Enriching[/] period {period_key}")
                if config.resume and steps_state.get("enrichment") == "completed":
                    try:
                        enriched_df = _load_enriched_table(enriched_path, period_df.schema())
                        logger.info("Loaded cached enrichment for %s", period_key)
                    except FileNotFoundError:
                        logger.info("Cached enrichment missing; regenerating %s", period_key)
                        if config.resume:
                            steps_state = _update_checkpoint_state(
                                resources, period_key, "enrichment", "in_progress"
                            )
                        enriched_df = enrich_dataframe(
                            period_df,
                            media_mapping,
                            resources.text_batch_client,
                            resources.vision_batch_client,
                            resources.enrichment_cache,
                            site_paths.docs_dir,
                            posts_dir,
                            model_config,
                        )
                        enriched_df.execute().to_csv(enriched_path, index=False)
                        if config.resume:
                            steps_state = _update_checkpoint_state(
                                resources, period_key, "enrichment", "completed"
                            )
                else:
                    if config.resume:
                        steps_state = _update_checkpoint_state(
                            resources, period_key, "enrichment", "in_progress"
                        )
                    enriched_df = enrich_dataframe(
                        period_df,
                        media_mapping,
                        resources.text_batch_client,
                        resources.vision_batch_client,
                        resources.enrichment_cache,
                        site_paths.docs_dir,
                        posts_dir,
                        model_config,
                    )
                    enriched_df.execute().to_csv(enriched_path, index=False)
                    if config.resume:
                        steps_state = _update_checkpoint_state(
                            resources, period_key, "enrichment", "completed"
                        )
            else:
                enriched_df = period_df
                enriched_df.execute().to_csv(enriched_path, index=False)

            if config.resume and steps_state.get("writing") == "completed":
                logger.info("Resuming posts for %s from existing files", period_key)
                existing_posts = sorted(posts_dir.glob(f"{period_key}-*.md"))
                result = {
                    "posts": [str(p) for p in existing_posts],
                    "profiles": [],
                }
            else:
                if config.resume:
                    steps_state = _update_checkpoint_state(
                        resources, period_key, "writing", "in_progress"
                    )
                result = write_posts_for_period(
                    enriched_df,
                    period_key,
                    client,
                    resources.embedding_batch_client,
                    posts_dir,
                    profiles_dir,
                    site_paths.rag_dir,
                    model_config,
                    enable_rag=True,
                    embedding_output_dimensionality=resources.embedding_dimensionality,
                    retrieval_mode=config.retrieval_mode,
                    retrieval_nprobe=config.retrieval_nprobe,
                    retrieval_overfetch=config.retrieval_overfetch,
                )
                if config.resume:
                    steps_state = _update_checkpoint_state(
                        resources, period_key, "writing", "completed"
                    )

            results[period_key] = cast(PeriodArtifacts, result)
            logger.info(
                f"[green]✔ Generated[/] {len(result.get('posts', []))} posts / {len(result.get('profiles', []))} profiles for {period_key}"
            )

        # Index all media enrichments into RAG (if enrichment was enabled)
        if config.enable_enrichment and results:
            logger.info("[bold cyan]📚 Indexing media enrichments into RAG...[/]")
            try:
                rag_dir = site_paths.rag_dir
                store = VectorStore(rag_dir / "chunks.parquet")
                media_chunks = index_all_media(
                    site_paths.docs_dir,
                    resources.embedding_batch_client,
                    store,
                    embedding_model=resources.embedding_batch_client.default_model,
                    output_dimensionality=resources.embedding_dimensionality,
                )
                if media_chunks > 0:
                    logger.info(f"[green]✓ Indexed[/] {media_chunks} media chunks into RAG")
                else:
                    logger.info("[yellow]No media enrichments to index for this run[/]")
            except Exception as e:
                logger.error(f"[red]Failed to index media into RAG:[/] {e}")

        return results
    finally:
        if resources is not None:
            resources.enrichment_cache.close()
        if client is not None:
            client.close()


def process_whatsapp_export(  # noqa: PLR0912, PLR0913
    zip_path: Path,
    output_dir: Path = Path("output"),
    period: str = "day",
    enable_enrichment: bool = True,
    from_date: date | None = None,
    to_date: date | None = None,
    timezone: ZoneInfo | None = None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> dict[str, PeriodArtifacts]:
    """Public entry point that manages DuckDB/Ibis backend state for processing."""

    output_dir = output_dir.expanduser().resolve()
    site_paths = resolve_site_paths(output_dir)

    runtime_db_path = site_paths.site_root / ".egregora" / "pipeline.duckdb"
    runtime_db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(runtime_db_path))
    backend = ibis.duckdb.from_connection(connection)

    options = getattr(ibis, "options", None)
    old_backend = getattr(options, "default_backend", None) if options else None

    try:
        if options is not None:
            options.default_backend = backend

        return _process_whatsapp_export(
            zip_path=zip_path,
            output_dir=output_dir,
            site_paths=site_paths,
            period=period,
            enable_enrichment=enable_enrichment,
            from_date=from_date,
            to_date=to_date,
            timezone=timezone,
            gemini_api_key=gemini_api_key,
            model=model,
            resume=resume,
            retrieval_mode=retrieval_mode,
            retrieval_nprobe=retrieval_nprobe,
            retrieval_overfetch=retrieval_overfetch,
        )
    finally:
        if options is not None:
            options.default_backend = old_backend
        connection.close()
