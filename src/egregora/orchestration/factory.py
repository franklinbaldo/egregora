"""Factory for creating pipeline resources and contexts.

This module handles the creation of database connections, contexts, and shared resources
for the write pipeline, decluttering the orchestration logic.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import ibis
from google import genai

from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.types import WriterResources
from egregora.config.exceptions import InvalidDatabaseUriError, SiteStructureError
from egregora.data_primitives.document import UrlContext
from egregora.database import initialize_database
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.profile_cache import scan_and_cache_all_documents
from egregora.database.repository import ContentRepository
from egregora.llm.usage import UsageTracker
from egregora.orchestration.cache import PipelineCache
from egregora.orchestration.context import (
    PipelineConfig,
    PipelineContext,
    PipelineRunParams,
    PipelineState,
)
from egregora.output_adapters import (
    OutputSinkRegistry,
    create_default_output_registry,
    create_output_sink,
)
from egregora.output_adapters.mkdocs import MkDocsPaths

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)


class PipelineFactory:
    """Factory for creating pipeline resources and contexts."""

    @staticmethod
    def create_context(run_params: PipelineRunParams) -> tuple[PipelineContext, Any]:
        """Create pipeline context with all resources and configuration.

        Args:
            run_params: Aggregated pipeline run parameters

        Returns:
            Tuple of (PipelineContext, pipeline_backend)
            The backend is returned for cleanup by the context manager.

        """
        resolved_output = run_params.output_dir.expanduser().resolve()

        refresh_tiers = {r.strip().lower() for r in (run_params.refresh or "").split(",") if r.strip()}
        site_paths = PipelineFactory.resolve_site_paths_or_raise(resolved_output, run_params.config)

        _runtime_db_uri, pipeline_backend = PipelineFactory.create_database_backends(
            site_paths.site_root, run_params.config
        )

        # Initialize database tables (CREATE TABLE IF NOT EXISTS)
        initialize_database(pipeline_backend)

        client_instance = run_params.client or PipelineFactory.create_gemini_client()
        cache_dir = Path(".egregora-cache") / site_paths.site_root.name
        cache = PipelineCache(cache_dir, refresh_tiers=refresh_tiers)
        site_paths.egregora_dir.mkdir(parents=True, exist_ok=True)
        storage = DuckDBStorageManager.from_ibis_backend(pipeline_backend)
        scan_and_cache_all_documents(
            storage,
            profiles_dir=site_paths.profiles_dir,
            posts_dir=site_paths.posts_dir,
        )
        repository = ContentRepository(storage)

        output_registry = create_default_output_registry()

        url_ctx = UrlContext(
            base_url="",
            site_prefix=site_paths.docs_prefix,
            base_path=site_paths.site_root,
        )

        adapter = PipelineFactory.create_output_adapter(
            config=run_params.config,
            output_dir=resolved_output,
            site_root=site_paths.site_root,
            registry=output_registry,
            url_context=url_ctx,
            storage=storage,
        )

        annotations_store = AnnotationStore(repository)

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
        )

        ctx = PipelineContext(config_obj, state)
        # Inject the already created adapter into the context
        ctx.state.output_sink = adapter

        return ctx, pipeline_backend

    @staticmethod
    def create_database_backends(
        site_root: Path,
        config: EgregoraConfig,
    ) -> tuple[str, Any]:
        """Create database backends for pipeline.

        Uses Ibis for database abstraction, allowing future migration to
        other databases (Postgres, SQLite, etc.) via connection strings.

        Args:
            site_root: Root directory for the site
            config: Egregora configuration

        Returns:
            Tuple of (runtime_db_uri, pipeline_backend).

        Notes:
            DuckDB file URIs with the pattern ``duckdb:///./relative/path.duckdb`` are
            resolved relative to ``site_root`` to keep configuration portable while
            still using proper connection strings.

        """

        def _validate_and_connect(value: str, setting_name: str) -> tuple[str, Any]:
            if not value:
                raise InvalidDatabaseUriError(value, f"Database setting '{setting_name}' must be non-empty.")

            parsed = urlparse(value)
            if not parsed.scheme:
                msg = (
                    f"Database setting '{setting_name}' must be provided as an "
                    "Ibis-compatible connection URI (e.g. 'duckdb:///absolute/path/to/file.duckdb' "
                    "or 'postgres://user:pass@host/db')."
                )
                raise InvalidDatabaseUriError(value, msg)

            if len(parsed.scheme) == 1 and value[1:3] in {":/", ":\\"}:
                msg = (
                    f"Database setting '{setting_name}' looks like a filesystem path. "
                    "Provide a full connection URI instead "
                    "(see the database settings documentation)."
                )
                raise InvalidDatabaseUriError(value, msg)

            normalized_value = value

            if parsed.scheme == "duckdb" and not parsed.netloc:
                path_value = parsed.path
                if path_value == "/:memory:":
                    # Normalize /:memory: to :memory: for Ibis/DuckDB compatibility
                    # to prevent it from trying to open a file at /:memory:
                    normalized_value = "duckdb://:memory:"
                elif path_value and path_value not in {":memory:", "memory", "memory:"}:
                    if path_value.startswith("/./"):
                        fs_path = (site_root / Path(path_value[3:])).resolve()
                    else:
                        fs_path = Path(path_value).resolve()
                    fs_path.parent.mkdir(parents=True, exist_ok=True)
                    if os.name == "nt":
                        # Windows paths need to avoid the leading slash (duckdb:///C:/)
                        # to prevent Ibis from prepending the current drive (C:/C:/).
                        # Using duckdb:C:/... (one slash after scheme) works.
                        normalized_value = f"duckdb:{fs_path.as_posix()}"
                    else:
                        normalized_value = f"duckdb:///{fs_path}"

            return normalized_value, ibis.connect(normalized_value)

        runtime_db_uri, pipeline_backend = _validate_and_connect(
            config.database.pipeline_db, "database.pipeline_db"
        )
        # runs_db removed as part of Essentialist simplification

        return runtime_db_uri, pipeline_backend

    @staticmethod
    def resolve_site_paths_or_raise(output_dir: Path, config: EgregoraConfig) -> MkDocsPaths:
        """Resolve site paths for the configured output format and validate structure."""
        output_dir = output_dir.expanduser().resolve()
        site_paths = MkDocsPaths(output_dir, config=config)

        # Default validation for MkDocs/standard structure
        mkdocs_path = site_paths.mkdocs_path
        if not mkdocs_path or not mkdocs_path.exists():
            msg = (
                f"No mkdocs.yml found for site at {output_dir}. "
                "Run 'egregora init <site-dir>' before processing exports."
            )
            raise SiteStructureError(str(output_dir), msg)

        docs_dir = site_paths.docs_dir
        if not docs_dir.exists():
            msg = (
                f"Docs directory not found: {docs_dir}. "
                "Re-run 'egregora init' to scaffold the MkDocs project."
            )
            raise SiteStructureError(str(docs_dir), msg)

        return site_paths

    @staticmethod
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

    @staticmethod
    def create_writer_resources(ctx: PipelineContext) -> WriterResources:
        """Build WriterResources from the pipeline context."""
        output = ctx.output_sink
        if output is None:
            msg = "Output adapter must be initialized before creating writer resources."
            raise RuntimeError(msg)

        profiles_dir = getattr(output, "profiles_dir", ctx.profiles_dir)
        journal_dir = getattr(output, "journal_dir", ctx.docs_dir / "journal")
        prompts_dir = ctx.site_root / ".egregora" / "prompts" if ctx.site_root else None

        profiles_dir.mkdir(parents=True, exist_ok=True)
        journal_dir.mkdir(parents=True, exist_ok=True)
        if prompts_dir:
            prompts_dir.mkdir(parents=True, exist_ok=True)

        retrieval_config = ctx.config.rag

        return WriterResources(
            output=output,
            output_registry=ctx.output_registry,
            annotations_store=ctx.annotations_store,
            storage=ctx.storage,
            embedding_model=ctx.embedding_model,
            retrieval_config=retrieval_config,
            profiles_dir=profiles_dir,
            journal_dir=journal_dir,
            prompts_dir=prompts_dir,
            client=ctx.client,
            usage=ctx.usage_tracker,
        )

    @staticmethod
    def create_gemini_client() -> genai.Client:
        """Create a Gemini client with retry configuration.

        The client reads the API key from GOOGLE_API_KEY environment variable automatically.
        """
        http_options = {
            "retry_options": {
                "attempts": 5,
                "initial_delay": 2.0,
                "max_delay": 15.0,
                "multiplier": 2.0,
                "http_status_codes": [429, 503],
            }
        }
        return genai.Client(http_options=http_options)
