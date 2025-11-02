"""Pydantic-AI powered writer agent.

This module experiments with migrating the writer workflow to Pydantic-AI.
It exposes ``write_posts_with_pydantic_agent`` which mirrors the signature of
``write_posts_for_period`` but routes the LLM conversation through a
``pydantic_ai.Agent`` instance. The implementation keeps the existing tool
surface (write_post, read/write_profile, search_media, annotate, banner)
so the rest of the pipeline can remain unchanged during the migration.

At the moment this backend is opt-in via the ``EGREGORA_LLM_BACKEND`` flag.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelMessagesTypeAdapter, RunContext
from pydantic_ai.models.google import GoogleModel

from egregora.augmentation.profiler import read_profile, write_profile
from egregora.generation.banner import generate_banner_for_post
from egregora.knowledge.annotations import AnnotationStore
from egregora.knowledge.rag import VectorStore, query_media
from egregora.orchestration.write_post import write_post

logger = logging.getLogger(__name__)


class PostMetadata(BaseModel):
    """Metadata schema for the write_post tool."""

    title: str
    slug: str
    date: str
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    authors: list[str] = Field(default_factory=list)
    category: str | None = None


class WritePostResult(BaseModel):
    status: str
    path: str


class WriteProfileResult(BaseModel):
    status: str
    path: str


class ReadProfileResult(BaseModel):
    content: str


class MediaItem(BaseModel):
    media_type: str | None = None
    media_path: str | None = None
    original_filename: str | None = None
    description: str | None = None
    similarity: float | None = None


class SearchMediaResult(BaseModel):
    results: list[MediaItem]


class AnnotationResult(BaseModel):
    status: str
    annotation_id: str | None = None
    parent_id: str | None = None
    parent_type: str | None = None


class BannerResult(BaseModel):
    status: str
    path: str | None = None


class WriterAgentReturn(BaseModel):
    """Final assistant response when the agent finishes."""

    summary: str | None = None
    notes: str | None = None


@dataclass
class WriterAgentState:
    """Mutable state shared with tool functions during a run."""

    period_date: str
    output_dir: Path
    profiles_dir: Path
    rag_dir: Path
    batch_client: Any
    embedding_model: str
    embedding_output_dimensionality: int
    retrieval_mode: str
    retrieval_nprobe: int | None
    retrieval_overfetch: int | None
    annotations_store: AnnotationStore | None

    saved_posts: list[str] = field(default_factory=list)
    saved_profiles: list[str] = field(default_factory=list)

    def record_post(self, path: str) -> None:
        logger.info("Writer agent saved post %s", path)
        self.saved_posts.append(path)

    def record_profile(self, path: str) -> None:
        logger.info("Writer agent saved profile %s", path)
        self.saved_profiles.append(path)


def _register_writer_tools(agent: Agent[WriterAgentReturn, WriterAgentState]) -> None:
    """Attach tool implementations to the agent."""

    @agent.tool
    def write_post_tool(
        ctx: RunContext[WriterAgentState],
        metadata: PostMetadata,
        content: str,
    ) -> WritePostResult:
        path = write_post(
            content=content,
            metadata=metadata.model_dump(exclude_none=True),
            output_dir=ctx.state.output_dir,
        )
        ctx.state.record_post(path)
        return WritePostResult(status="success", path=path)

    @agent.tool
    def read_profile_tool(
        ctx: RunContext[WriterAgentState],
        author_uuid: str,
    ) -> ReadProfileResult:
        content = read_profile(author_uuid, ctx.state.profiles_dir)
        if not content:
            content = "No profile exists yet."
        return ReadProfileResult(content=content)

    @agent.tool
    def write_profile_tool(
        ctx: RunContext[WriterAgentState],
        author_uuid: str,
        content: str,
    ) -> WriteProfileResult:
        path = write_profile(author_uuid, content, ctx.state.profiles_dir)
        ctx.state.record_profile(path)
        return WriteProfileResult(status="success", path=path)

    @agent.tool
    def search_media_tool(
        ctx: RunContext[WriterAgentState],
        query: str,
        media_types: list[str] | None = None,
        limit: int = 5,
    ) -> SearchMediaResult:
        store = VectorStore(ctx.state.rag_dir / "chunks.parquet")
        results = query_media(
            query=query,
            batch_client=ctx.state.batch_client,
            store=store,
            media_types=media_types,
            top_k=limit,
            min_similarity=0.7,
            embedding_model=ctx.state.embedding_model,
            output_dimensionality=ctx.state.embedding_output_dimensionality,
            retrieval_mode=ctx.state.retrieval_mode,
            retrieval_nprobe=ctx.state.retrieval_nprobe,
            retrieval_overfetch=ctx.state.retrieval_overfetch,
        )
        executed = results.execute()
        items: list[MediaItem] = []
        for _, row in executed.iterrows():
            items.append(
                MediaItem(
                    media_type=row.get("media_type"),
                    media_path=row.get("media_path"),
                    original_filename=row.get("original_filename"),
                    description=(str(row.get("content", "")) or "")[:500],
                    similarity=float(row.get("similarity")) if row.get("similarity") is not None else None,
                )
            )
        if not items:
            logger.info("Writer agent search_media returned no matches for query %s", query)
        return SearchMediaResult(results=items)

    @agent.tool
    def annotate_conversation_tool(
        ctx: RunContext[WriterAgentState],
        parent_id: str,
        parent_type: str,
        commentary: str,
    ) -> AnnotationResult:
        if ctx.state.annotations_store is None:
            raise RuntimeError("Annotation store is not configured")
        annotation = ctx.state.annotations_store.save_annotation(
            parent_id=parent_id,
            parent_type=parent_type,
            commentary=commentary,
        )
        return AnnotationResult(
            status="ok",
            annotation_id=annotation.id,
            parent_id=annotation.parent_id,
            parent_type=annotation.parent_type,
        )

    @agent.tool
    def generate_banner_tool(
        ctx: RunContext[WriterAgentState],
        post_slug: str,
        title: str,
        summary: str,
    ) -> BannerResult:
        banner_path = generate_banner_for_post(
            post_title=title,
            post_summary=summary,
            output_dir=ctx.state.output_dir,
            slug=post_slug,
        )
        if banner_path:
            return BannerResult(status="success", path=str(banner_path))
        return BannerResult(status="skipped", path=None)


def write_posts_with_pydantic_agent(  # noqa: PLR0913
    *,
    prompt: str,
    model_name: str,
    period_date: str,
    output_dir: Path,
    profiles_dir: Path,
    rag_dir: Path,
    batch_client: Any,
    embedding_model: str,
    embedding_output_dimensionality: int,
    retrieval_mode: str,
    retrieval_nprobe: int | None,
    retrieval_overfetch: int | None,
    annotations_store: AnnotationStore | None,
    agent_model: Any | None = None,
) -> tuple[list[str], list[str]]:
    """
    Execute the writer flow using Pydantic-AI agent tooling.

    Returns:
        Tuple (saved_posts, saved_profiles, freeform_content_path)
    """
    logger.info("Running writer via Pydantic-AI backend")
    agent = Agent(
        model=agent_model or GoogleModel(model_name),
        result_type=WriterAgentReturn,
    )
    _register_writer_tools(agent)

    state = WriterAgentState(
        period_date=period_date,
        output_dir=output_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        batch_client=batch_client,
        embedding_model=embedding_model,
        embedding_output_dimensionality=embedding_output_dimensionality,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        annotations_store=annotations_store,
    )

    try:
        result = agent.run_sync(prompt, context=state)
        logger.info("Writer agent finished with summary: %s", getattr(result.data, "summary", None))
        record_dir = os.environ.get("EGREGORA_LLM_RECORD_DIR")
        if record_dir:
            output_path = Path(record_dir).expanduser()
            output_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = output_path / f"writer-{period_date}-{timestamp}.json"
            try:
                payload = ModelMessagesTypeAdapter.dump_json(result.all_messages())
                filename.write_bytes(payload)
                logger.info("Recorded writer agent conversation to %s", filename)
            except Exception as record_exc:  # pragma: no cover - best effort recording
                logger.warning("Failed to persist writer agent messages: %s", record_exc)
    except Exception as exc:  # pragma: no cover - Pydantic-AI wraps HTTP errors
        logger.error("Pydantic writer agent failed: %s", exc)
        raise

    return state.saved_posts, state.saved_profiles
