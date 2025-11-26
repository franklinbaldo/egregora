"""Factory for creating pipeline resources and contexts.

This module handles the creation of database connections, contexts, and shared resources
for the write pipeline, decluttering the orchestration logic.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import ibis
from google import genai

from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.shared.rag import VectorStore
from egregora.agents.writer import WriterResources
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.protocols import UrlContext
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.orchestration.context import PipelineConfig, PipelineContext, PipelineState
from egregora.output_adapters import create_output_format, output_registry
from egregora.output_adapters.mkdocs import derive_mkdocs_paths
from egregora.output_adapters.mkdocs.paths import compute_site_prefix
from egregora.utils.cache import PipelineCache
from egregora.utils.metrics import UsageTracker
from egregora.utils.quota import QuotaTracker
from egregora.utils.rate_limit import AsyncRateLimiter

logger = logging.getLogger(__name__)


class PipelineFactory:
    """Factory for creating pipeline resources and contexts."""

    @staticmethod
    def create_context(  # noqa: PLR0913
        output_dir: Path,
        config: EgregoraConfig,
        client: genai.Client | None,
        run_id: uuid.UUID,
        start_time: datetime,
        source_type: str,
        input_path: Path,
        refresh: str | None = None,
    ) -> tuple[PipelineContext, any, any]:
        """Create pipeline context with all resources and configuration.

        Args:
            output_dir: Output directory for the pipeline
            config: Egregora configuration
            client: Optional existing Gemini client (reads GOOGLE_API_KEY env if None)
            run_id: Unique run identifier
            start_time: Run start timestamp
            source_type: Source type (e.g., "whatsapp", "slack")
            input_path: Path to input file
            refresh: Optional comma-separated list of cache tiers to refresh

        Returns:
            Tuple of (PipelineContext, pipeline_backend, runs_backend)
            The backends are returned for cleanup by the context manager.

        """
        resolved_output = output_dir.expanduser().resolve()

        refresh_tiers = {r.strip().lower() for r in (refresh or "").split(",") if r.strip()}
        site_paths = PipelineFactory.resolve_site_paths_or_raise(resolved_output, config)

        _runtime_db_uri, pipeline_backend, runs_backend = PipelineFactory.create_database_backends(
            site_paths["site_root"], config
        )

        # Initialize database tables (CREATE TABLE IF NOT EXISTS)
        from egregora.database import initialize_database

        initialize_database(pipeline_backend)

        client_instance = client or PipelineFactory.create_gemini_client()
        cache_dir = Path(".egregora-cache") / site_paths["site_root"].name
        cache = PipelineCache(cache_dir, refresh_tiers=refresh_tiers)
        site_paths["egregora_dir"].mkdir(parents=True, exist_ok=True)
        db_file = site_paths["egregora_dir"] / "app.duckdb"
        storage = DuckDBStorageManager(db_path=db_file)

        rag_store = None
        if config.rag.enabled:
            rag_dir = site_paths["rag_dir"]
            rag_dir.mkdir(parents=True, exist_ok=True)
            rag_store = VectorStore(rag_dir / "chunks.parquet", storage=storage)

        annotations_store = AnnotationStore(storage)

        quota_tracker = QuotaTracker(site_paths["egregora_dir"], config.quota.daily_llm_requests)
        rate_limit = AsyncRateLimiter(config.quota.per_second_limit)

        from egregora.data_primitives.protocols import UrlContext

        url_ctx = UrlContext(
            base_url="",
            site_prefix=compute_site_prefix(site_paths["site_root"], site_paths["docs_dir"]),
            base_path=site_paths["site_root"],
        )

        config_obj = PipelineConfig(
            config=config,
            output_dir=resolved_output,
            site_root=site_paths["site_root"],
            docs_dir=site_paths["docs_dir"],
            posts_dir=site_paths["posts_dir"],
            profiles_dir=site_paths["profiles_dir"],
            media_dir=site_paths["media_dir"],
            url_context=url_ctx,
        )

        state = PipelineState(
            run_id=run_id,
            start_time=start_time,
            source_type=source_type,
            input_path=input_path,
            client=client_instance,
            storage=storage,
            cache=cache,
            rag_store=rag_store,
            annotations_store=annotations_store,
            quota_tracker=quota_tracker,
            rate_limit=rate_limit,
            usage_tracker=UsageTracker(),
        )

        ctx = PipelineContext(config_obj, state)

        return ctx, pipeline_backend, runs_backend

    @staticmethod
    def create_database_backends(
        site_root: Path,
        config: EgregoraConfig,
    ) -> tuple[str, any, any]:
        """Create database backends for pipeline and runs tracking.

        Uses Ibis for database abstraction, allowing future migration to
        other databases (Postgres, SQLite, etc.) via connection strings.

        Args:
            site_root: Root directory for the site
            config: Egregora configuration

        Returns:
            Tuple of (runtime_db_uri, pipeline_backend, runs_backend).

        Notes:
            DuckDB file URIs with the pattern ``duckdb:///./relative/path.duckdb`` are
            resolved relative to ``site_root`` to keep configuration portable while
            still using proper connection strings.

        """

        def _validate_and_connect(value: str, setting_name: str) -> tuple[str, any]:
            if not value:
                msg = f"Database setting '{setting_name}' must be a non-empty connection URI."
                raise ValueError(msg)

            parsed = urlparse(value)
            if not parsed.scheme:
                msg = (
                    "Database setting '{setting}' must be provided as an Ibis-compatible connection "
                    "URI (e.g. 'duckdb:///absolute/path/to/file.duckdb' or 'postgres://user:pass@host/db')."
                )
                raise ValueError(msg.format(setting=setting_name))

            if len(parsed.scheme) == 1 and value[1:3] in {":/", ":\\"}:
                msg = (
                    "Database setting '{setting}' looks like a filesystem path. Provide a full connection "
                    "URI instead (see the database settings documentation)."
                )
                raise ValueError(msg.format(setting=setting_name))

            normalized_value = value

            if parsed.scheme == "duckdb" and not parsed.netloc:
                path_value = parsed.path
                if path_value and path_value not in {"/:memory:", ":memory:", "memory", "memory:"}:
                    if path_value.startswith("/./"):
                        fs_path = (site_root / Path(path_value[3:])).resolve()
                    else:
                        fs_path = Path(path_value).resolve()
                    fs_path.parent.mkdir(parents=True, exist_ok=True)
                    normalized_value = f"duckdb:///{fs_path}"

            return normalized_value, ibis.connect(normalized_value)

        runtime_db_uri, pipeline_backend = _validate_and_connect(
            config.database.pipeline_db, "database.pipeline_db"
        )
        _runs_db_uri, runs_backend = _validate_and_connect(config.database.runs_db, "database.runs_db")

        return runtime_db_uri, pipeline_backend, runs_backend

    @staticmethod
    def resolve_site_paths_or_raise(output_dir: Path, config: EgregoraConfig) -> dict[str, any]:
        """Resolve site paths for the configured output format and validate structure."""
        output_dir = output_dir.expanduser().resolve()
        site_paths = derive_mkdocs_paths(output_dir, config=config)

        # Default validation for MkDocs/standard structure
        mkdocs_path = site_paths.get("mkdocs_path")
        if not mkdocs_path or not mkdocs_path.exists():
            msg = (
                f"No mkdocs.yml found for site at {output_dir}. "
                "Run 'egregora init <site-dir>' before processing exports."
            )
            raise ValueError(msg)

        docs_dir = site_paths["docs_dir"]
        if not docs_dir.exists():
            msg = f"Docs directory not found: {docs_dir}. Re-run 'egregora init' to scaffold the MkDocs project."
            raise ValueError(msg)

        return site_paths

    @staticmethod
    def create_output_adapter(
        config: EgregoraConfig,
        output_dir: Path,
        *,
        site_root: Path | None = None,
        url_context: UrlContext | None = None,
    ):
        """Create and initialize the output adapter for the pipeline."""
        resolved_output = output_dir.expanduser().resolve()
        site_paths = derive_mkdocs_paths(resolved_output, config=config)

        root = site_root or site_paths["site_root"]

        adapter = output_registry.detect_format(root)
        if adapter is None:
            adapter = create_output_format(root, format_type="mkdocs")

        adapter.initialize(root, url_context=url_context)
        return adapter

    @staticmethod
    def create_writer_resources(ctx: PipelineContext) -> WriterResources:
        """Build WriterResources from the pipeline context."""
        output = ctx.output_format
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
            rag_store=ctx.rag_store if ctx.enable_rag else None,
            annotations_store=ctx.annotations_store,
            storage=ctx.storage,
            embedding_model=ctx.embedding_model,
            retrieval_config=retrieval_config,
            profiles_dir=profiles_dir,
            journal_dir=journal_dir,
            prompts_dir=prompts_dir,
            client=ctx.client,
            quota=ctx.quota_tracker,
            usage=ctx.usage_tracker,
            rate_limit=ctx.rate_limit,
        )

    @staticmethod
    def create_gemini_client() -> genai.Client:
        """Create a Gemini client with retry configuration.

        The client reads the API key from GOOGLE_API_KEY environment variable automatically.
        """
        http_options = genai.types.HttpOptions(
            retryOptions=genai.types.HttpRetryOptions(
                attempts=5,
                initialDelay=2.0,
                maxDelay=15.0,
                expBase=2.0,
                httpStatusCodes=[429, 503],
            )
        )
        return genai.Client(http_options=http_options)
