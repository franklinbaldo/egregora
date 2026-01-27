"""Resource creation for the Egregora pipeline.

This module handles the creation of shared resources like WriterResources,
separating instantiation logic from the factory class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from egregora.agents.types import WriterResources

if TYPE_CHECKING:
    from egregora.orchestration.context import PipelineContext

__all__ = ["create_writer_resources"]


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
