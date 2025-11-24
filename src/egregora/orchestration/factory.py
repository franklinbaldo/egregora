"""Factory for constructing pipeline dependencies.

This module isolates dependency creation logic from the orchestration layer,
providing a single place to wire up components.
"""

from __future__ import annotations

from pathlib import Path

from egregora.agents.writer import WriterResources
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.protocols import OutputSink, UrlContext
from egregora.orchestration.context import PipelineContext
from egregora.output_adapters.mkdocs import MkDocsAdapter


class PipelineFactory:
    """Factory for creating pipeline components and resources."""

    @staticmethod
    def create_output_adapter(
        config: EgregoraConfig,
        output_dir: Path,
        site_root: Path | None = None,
        url_context: UrlContext | None = None,
    ) -> OutputSink:
        """Create and initialize an output adapter based on configuration."""
        from egregora.output_adapters import create_output_format

        storage_root = site_root if site_root else output_dir
        format_type = config.output.format

        if format_type == "mkdocs":
            adapter = MkDocsAdapter()
            # If no context provided, build a default one
            if url_context is None:
                prefix = ""
                if site_root:
                    # Best-effort prefix calculation if we know the structure
                    try:
                        # We don't have docs_dir here easily without re-deriving paths
                        # But MkDocsAdapter.initialize calls derive_mkdocs_paths internally if we just pass site_root?
                        # Actually MkDocsAdapter.initialize takes (site_root, url_context)
                        # We'll let it use the one we pass or default
                        pass
                    except Exception:
                        pass

                url_context = UrlContext(base_url="", site_prefix=prefix, base_path=storage_root)

            adapter.initialize(site_root=storage_root, url_context=url_context)
            return adapter

        return create_output_format(storage_root, format_type=format_type)

    @staticmethod
    def create_writer_resources(ctx: PipelineContext) -> WriterResources:
        """Create writer resources from pipeline context."""
        # Ensure output sink is initialized (it should be if coming from ctx)
        output_format = ctx.output_format
        if not output_format:
            # Fallback: try to create it if missing (legacy path)
            output_format = PipelineFactory.create_output_adapter(
                ctx.config, ctx.output_dir, ctx.site_root, ctx.url_context
            )

        prompts_dir = ctx.site_root / ".egregora" / "prompts" if ctx.site_root else None
        journal_dir = (
            ctx.site_root / ctx.config.paths.journal_dir if ctx.site_root else ctx.output_dir / "journal"
        )

        return WriterResources(
            output=output_format,
            rag_store=ctx.rag_store,
            annotations_store=ctx.annotations_store,
            storage=ctx.storage,
            embedding_model=ctx.embedding_model,
            retrieval_config=ctx.config.rag,
            profiles_dir=ctx.profiles_dir,
            journal_dir=journal_dir,
            prompts_dir=prompts_dir,
            client=ctx.client,
            quota=ctx.quota_tracker,
            usage=ctx.usage_tracker,
            rate_limit=ctx.rate_limit,
        )
