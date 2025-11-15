"""Tool definitions for the Pydantic-AI powered writer agent."""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from pydantic_ai import RunContext

from egregora.agents.banner import generate_banner_for_post
from egregora.data_primitives.document import Document, DocumentType
from egregora.agents.shared.rag.retriever import query_media
from .schemas import (
    WriterAgentState,
    WriterAgentReturn,
    PostMetadata,
    WritePostResult,
    ReadProfileResult,
    WriteProfileResult,
    SearchMediaResult,
    MediaItem,
    AnnotationResult,
    BannerResult,
)

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


def register_writer_tools(
    agent: Agent[WriterAgentState, WriterAgentReturn],
    *,
    enable_banner: bool = False,
    enable_rag: bool = False,
) -> None:
    """Attach tool implementations to the agent."""

    @agent.tool
    def write_post_tool(
        ctx: RunContext[WriterAgentState], metadata: PostMetadata, content: str
    ) -> WritePostResult:
        doc = Document(
            content=content,
            type=DocumentType.POST,
            metadata=metadata.model_dump(exclude_none=True),
            source_window=ctx.deps.window_id,
        )
        url = ctx.deps.url_convention.canonical_url(doc, ctx.deps.url_context)
        ctx.deps.output_format.serve(doc)
        logger.info("Writer agent saved post at URL: %s (doc_id: %s)", url, doc.document_id)
        return WritePostResult(status="success", path=url)

    @agent.tool
    def read_profile_tool(ctx: RunContext[WriterAgentState], author_uuid: str) -> ReadProfileResult:
        doc = ctx.deps.output_format.read_document(DocumentType.PROFILE, author_uuid)
        content = doc.content if doc else "No profile exists yet."
        return ReadProfileResult(content=content)

    @agent.tool
    def write_profile_tool(
        ctx: RunContext[WriterAgentState], author_uuid: str, content: str
    ) -> WriteProfileResult:
        doc = Document(
            content=content,
            type=DocumentType.PROFILE,
            metadata={"uuid": author_uuid},
            source_window=ctx.deps.window_id,
        )
        url = ctx.deps.url_convention.canonical_url(doc, ctx.deps.url_context)
        ctx.deps.output_format.serve(doc)
        logger.info("Writer agent saved profile at URL: %s (doc_id: %s)", url, doc.document_id)
        return WriteProfileResult(status="success", path=url)

    if enable_rag:
        @agent.tool
        def search_media_tool(
            ctx: RunContext[WriterAgentState],
            query: str,
            media_types: list[str] | None = None,
            limit: int = 5,
        ) -> SearchMediaResult:
            results = query_media(
                query=query,
                store=ctx.deps.rag_store,
                media_types=media_types,
                top_k=limit,
                min_similarity_threshold=0.7,
                embedding_model=ctx.deps.embedding_model,
                retrieval_mode=ctx.deps.retrieval_mode,
                retrieval_nprobe=ctx.deps.retrieval_nprobe,
                retrieval_overfetch=ctx.deps.retrieval_overfetch,
            )
            df = results.execute()
            items = [MediaItem(**row) for row in df.to_dict("records")]
            return SearchMediaResult(results=items)

    @agent.tool
    def annotate_conversation_tool(
        ctx: RunContext[WriterAgentState], parent_id: str, parent_type: str, commentary: str
    ) -> AnnotationResult:
        if ctx.deps.annotations_store is None:
            raise RuntimeError("Annotation store is not configured")
        annotation = ctx.deps.annotations_store.save_annotation(
            parent_id=parent_id, parent_type=parent_type, commentary=commentary
        )
        return AnnotationResult(
            status="success",
            annotation_id=annotation.id,
            parent_id=annotation.parent_id,
            parent_type=annotation.parent_type,
        )

    if enable_banner:
        @agent.tool
        def generate_banner_tool(
            ctx: RunContext[WriterAgentState], post_slug: str, title: str, summary: str
        ) -> BannerResult:
            banner_output_dir = ctx.deps.output_format.media_dir / "images"
            banner_path = generate_banner_for_post(
                post_title=title, post_summary=summary, output_dir=banner_output_dir, slug=post_slug
            )
            if banner_path:
                return BannerResult(status="success", path=str(banner_path))
            return BannerResult(status="failed", path=None)
