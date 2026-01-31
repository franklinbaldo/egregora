"""Setup logic for the Egregora write pipeline.

This module handles:
- Pipeline environment provisioning
- Database connection and backend creation
- Site path resolution and initialization
- API key validation
- Global rate limiter initialization
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import ibis
from google import genai
from google.genai import types
from rich.console import Console

from egregora.agents.shared.annotations import AnnotationStore
from egregora.config.exceptions import ApiKeyNotFoundError
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import UrlContext
from egregora.database import initialize_database
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.task_store import TaskStore
from egregora.database.utils import resolve_db_uri
from egregora.llm.api_keys import get_google_api_keys, validate_gemini_api_key
from egregora.llm.rate_limit import init_rate_limiter
from egregora.llm.usage import UsageTracker
from egregora.orchestration.cache import PipelineCache
from egregora.orchestration.context import PipelineConfig, PipelineContext, PipelineRunParams, PipelineState
from egregora.orchestration.exceptions import ApiKeyInvalidError
from egregora.output_sinks import (
    OutputSinkRegistry,
    create_default_output_registry,
    create_output_sink,
)
from egregora.output_sinks.mkdocs import MkDocsPaths
from egregora.output_sinks.mkdocs.scaffolding import MkDocsSiteScaffolder

try:
    import dotenv
except ImportError:
    dotenv = None

logger = logging.getLogger(__name__)
console = Console()


def _load_dotenv_if_available(output_dir: Path) -> None:
    if dotenv:
        dotenv.load_dotenv(output_dir / ".env")
        dotenv.load_dotenv()  # Check CWD as well


def ensure_site_initialized(output_dir: Path) -> None:
    """Ensure the site is initialized with configuration."""
    config_path = output_dir / ".egregora.toml"

    if not config_path.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Initializing site in %s", output_dir)
        scaffolder = MkDocsSiteScaffolder()
        scaffolder.scaffold_site(output_dir, site_name=output_dir.name)


def validate_api_key(output_dir: Path) -> None:
    """Validate that API key is set and valid.

    Raises:
        ApiKeyNotFoundError: If no API key is found.
        ApiKeyInvalidError: If no valid API key is found among candidates.
    """
    skip_validation = os.getenv("EGREGORA_SKIP_API_KEY_VALIDATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }

    api_keys = get_google_api_keys()
    if not api_keys:
        _load_dotenv_if_available(output_dir)
        api_keys = get_google_api_keys()

    if not api_keys:
        raise ApiKeyNotFoundError("GOOGLE_API_KEY")

    if skip_validation:
        if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = api_keys[0]
        return

    console.print("[cyan]Validating Gemini API key...[/cyan]")
    validation_errors: list[str] = []
    for key in api_keys:
        try:
            validate_gemini_api_key(key)
            if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
                os.environ["GOOGLE_API_KEY"] = key
            console.print("[green]✓ API key validated successfully[/green]")
            return
        except ValueError as e:
            validation_errors.append(str(e))
        except ImportError as e:
            raise ApiKeyInvalidError(f"Import error validating key: {e}", validation_errors=[str(e)]) from e

    raise ApiKeyInvalidError("No valid API key found", validation_errors=validation_errors)


def _resolve_pipeline_site_paths(output_dir: Path, config: EgregoraConfig) -> MkDocsPaths:
    """Resolve site paths for the configured output format."""
    output_dir = output_dir.expanduser().resolve()
    return MkDocsPaths(output_dir, config=config)


def _resolve_site_paths_or_raise(output_dir: Path, config: EgregoraConfig) -> MkDocsPaths:
    """Resolve site paths for the configured output format and validate structure."""
    site_paths = _resolve_pipeline_site_paths(output_dir, config)

    # Default validation for MkDocs/standard structure
    mkdocs_path = site_paths.mkdocs_path
    if not mkdocs_path or not mkdocs_path.exists():
        msg = (
            f"No mkdocs.yml found for site at {output_dir}. "
            "Run 'egregora init <site-dir>' before processing exports."
        )
        raise ValueError(msg)

    docs_dir = site_paths.docs_dir
    if not docs_dir.exists():
        msg = f"Docs directory not found: {docs_dir}. Re-run 'egregora init' to scaffold the MkDocs project."
        raise ValueError(msg)

    return site_paths


def _validate_and_connect(value: str | None, setting_name: str, site_root: Path) -> tuple[str, Any]:
    """Validate database URI and connect to the backend.

    Args:
        value: Database URI string
        setting_name: Name of the setting for error messages
        site_root: Site root directory for resolving relative paths

    Returns:
        Tuple of (resolved_uri, backend_connection)

    """
    if not value:
        msg = f"Database setting '{setting_name}' must be a non-empty connection URI."
        raise ValueError(msg)

    parsed = urlparse(value)
    if not parsed.scheme:
        msg = (
            f"Database setting '{setting_name}' must be provided as an Ibis-compatible connection "
            "URI (e.g. 'duckdb:///absolute/path/to/file.duckdb' or 'postgres://user:pass@host/db')."
        )
        raise ValueError(msg)

    if len(parsed.scheme) == 1 and value[1:3] in {":/", ":\\"}:
        msg = (
            f"Database setting '{setting_name}' looks like a filesystem path. Provide a full connection "
            "URI instead (see the database settings documentation)."
        )
        raise ValueError(msg)

    normalized_value = resolve_db_uri(value, site_root)
    return normalized_value, ibis.connect(normalized_value)


def _create_database_backend(
    site_root: Path,
    config: EgregoraConfig,
) -> tuple[str, Any]:
    """Create the main database backend for the pipeline.

    Returns a tuple of the resolved database URI and the Ibis backend connection.
    """
    return _validate_and_connect(config.database.pipeline_db, "database.pipeline_db", site_root)


def _create_gemini_client(api_key: str | None = None) -> genai.Client:
    """Create a Gemini client with retry configuration."""
    http_options = {
        "retry_options": {
            "attempts": 5,
            "initial_delay": 2.0,
            "max_delay": 15.0,
            "http_status_codes": [429, 503],
        }
    }
    return genai.Client(api_key=api_key, http_options=cast("Any", http_options))


def _get_safety_settings() -> list[types.SafetySetting]:
    """Get standard safety settings to avoid blocking content."""
    return [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
    ]


def _init_global_rate_limiter(quota_config: Any) -> None:
    """Initialize the global rate limiter."""
    init_rate_limiter(
        requests_per_second=quota_config.per_second_limit,
        max_concurrency=quota_config.concurrency,
    )


def _create_pipeline_context(run_params: PipelineRunParams) -> tuple[PipelineContext, Any]:
    """Create pipeline context with all resources and configuration.

    Returns a tuple of the PipelineContext and the pipeline_backend for cleanup.
    """
    resolved_output = run_params.output_dir.expanduser().resolve()

    refresh_tiers = {r.strip().lower() for r in (run_params.refresh or "").split(",") if r.strip()}
    site_paths = _resolve_site_paths_or_raise(resolved_output, run_params.config)
    _runtime_db_uri, pipeline_backend = _create_database_backend(site_paths.site_root, run_params.config)

    # Initialize database tables (CREATE TABLE IF NOT EXISTS)
    initialize_database(pipeline_backend)

    client_instance = run_params.client or _create_gemini_client()
    cache_path = Path(run_params.config.paths.cache_dir)
    cache_dir = cache_path if cache_path.is_absolute() else site_paths.site_root / cache_path
    cache = PipelineCache(cache_dir, refresh_tiers=refresh_tiers)
    site_paths.egregora_dir.mkdir(parents=True, exist_ok=True)

    # Use the pipeline backend for storage to ensure we share the same connection
    # This prevents "read-only transaction" errors and database invalidation
    storage = DuckDBStorageManager.from_ibis_backend(pipeline_backend)
    annotations_store = AnnotationStore(storage)

    # Initialize TaskStore for async operations
    task_store = TaskStore(storage)

    _init_global_rate_limiter(run_params.config.quota)

    output_registry = create_default_output_registry()

    url_ctx = UrlContext(
        base_url="",
        site_prefix="",  # FIX: Empty prefix because MkDocsAdapter prepends media_dir
        base_path=site_paths.site_root,
    )

    config_obj = PipelineConfig(
        config=run_params.config,
        output_dir=resolved_output,
        site_root=site_paths.site_root,
        docs_dir=site_paths.docs_dir,
        posts_dir=site_paths.posts_dir,
        profiles_dir=site_paths.profiles_dir,
        media_dir=site_paths.media_dir,
        url_context=url_ctx,
    )

    state = PipelineState(
        run_id=run_params.run_id,
        start_time=run_params.start_time,
        source_type=run_params.source_type,
        input_path=run_params.input_path,
        client=client_instance,
        storage=storage,
        cache=cache,
        annotations_store=annotations_store,
        usage_tracker=UsageTracker(),
        output_registry=output_registry,
        smoke_test=run_params.smoke_test,
    )

    # Inject TaskStore into state/context
    state.task_store = task_store

    ctx = PipelineContext(config_obj, state)

    return ctx, pipeline_backend


def create_output_adapter(
    config: EgregoraConfig,
    output_dir: Path,
    *,
    site_root: Path | None = None,
    registry: OutputSinkRegistry | None = None,
    url_context: UrlContext | None = None,
    storage: Any | None = None,
) -> Any:
    """Create and initialize the output adapter for the pipeline.

    Args:
        config: Egregora configuration
        output_dir: Output directory
        site_root: Site root directory (optional)
        registry: Output sink registry (optional)
        url_context: URL context for canonical URLs (optional)
        storage: DuckDBStorageManager for database-backed reading (optional)

    Returns:
        Initialized output adapter

    """
    resolved_output = output_dir.expanduser().resolve()
    site_paths = MkDocsPaths(resolved_output, config=config)

    root = site_root or site_paths.site_root

    registry = registry or create_default_output_registry()

    adapter = registry.detect_format(root)
    if adapter is None:
        adapter = create_output_sink(root, format_type="mkdocs", registry=registry)

    adapter.initialize(root, url_context=url_context, storage=storage)
    return adapter


@contextmanager
def pipeline_environment(run_params: PipelineRunParams) -> Iterator[PipelineContext]:
    """Context manager that provisions and tears down pipeline resources."""
    options = getattr(ibis, "options", None)
    old_backend = getattr(options, "default_backend", None) if options else None
    ctx, pipeline_backend = _create_pipeline_context(run_params)

    if options is not None:
        options.default_backend = pipeline_backend

    try:
        yield ctx
    finally:
        # Explicitly close the GenAI client to prevent "Event loop is closed" errors
        # caused by unclosed async resources in httpcore/anyio during shutdown
        if ctx.state.client:
            client_close = getattr(ctx.state.client, "close", None)
            if callable(client_close):
                with suppress(Exception):
                    # Best effort cleanup, ignore errors
                    client_close()

        try:
            ctx.cache.close()
        finally:
            if options is not None:
                options.default_backend = old_backend

            backend_close = getattr(pipeline_backend, "close", None)
            if callable(backend_close):
                backend_close()
            elif hasattr(pipeline_backend, "con") and hasattr(pipeline_backend.con, "close"):
                pipeline_backend.con.close()
