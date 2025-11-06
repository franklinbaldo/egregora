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

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

try:  # Prefer the richer adapter API when available.
    from pydantic_ai import Agent, ModelMessagesTypeAdapter, RunContext
except ImportError:  # pragma: no cover - backwards compatibility for older releases
    from pydantic_ai import Agent, RunContext  # type: ignore

    class ModelMessagesTypeAdapter:  # type: ignore[override]
        """Lightweight shim mirroring the adapter interface used in tests."""

        @staticmethod
        def dump_json(messages: Any) -> str:
            if hasattr(messages, "model_dump_json"):
                return messages.model_dump_json(indent=2)
            if hasattr(messages, "model_dump"):
                return json.dumps(messages.model_dump(mode="json"), indent=2)
            if hasattr(messages, "to_json"):
                return messages.to_json(indent=2)
            return json.dumps(messages, indent=2, default=str)


try:
    from pydantic_ai.models.gemini import GeminiModel
except ImportError:  # pragma: no cover - newer SDK uses google module
    from pydantic_ai.models.google import GoogleModel as GeminiModel  # type: ignore

from egregora.agents.banner import generate_banner_for_post
from egregora.agents.tools.annotations import AnnotationStore
from egregora.agents.tools.profiler import read_profile, write_profile
from egregora.agents.tools.rag import VectorStore, query_media
from egregora.database.streaming import stream_ibis
from egregora.utils.logfire_config import logfire_info, logfire_span
from egregora.utils.write_post import write_post

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


class WriterAgentState(BaseModel):
    """Mutable state shared with tool functions during a run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

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

    saved_posts: list[str] = Field(default_factory=list)
    saved_profiles: list[str] = Field(default_factory=list)

    def record_post(self, path: str) -> None:
        logger.info("Writer agent saved post %s", path)
        self.saved_posts.append(path)

    def record_profile(self, path: str) -> None:
        logger.info("Writer agent saved profile %s", path)
        self.saved_profiles.append(path)


def _register_writer_tools(agent: Agent[WriterAgentState, WriterAgentReturn]) -> None:
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
            output_dir=ctx.deps.output_dir,
        )
        ctx.deps.record_post(path)
        return WritePostResult(status="success", path=path)

    @agent.tool
    def read_profile_tool(
        ctx: RunContext[WriterAgentState],
        author_uuid: str,
    ) -> ReadProfileResult:
        content = read_profile(author_uuid, ctx.deps.profiles_dir)
        if not content:
            content = "No profile exists yet."
        return ReadProfileResult(content=content)

    @agent.tool
    def write_profile_tool(
        ctx: RunContext[WriterAgentState],
        author_uuid: str,
        content: str,
    ) -> WriteProfileResult:
        path = write_profile(author_uuid, content, ctx.deps.profiles_dir)
        ctx.deps.record_profile(path)
        return WriteProfileResult(status="success", path=path)

    @agent.tool
    def search_media_tool(
        ctx: RunContext[WriterAgentState],
        query: str,
        media_types: list[str] | None = None,
        limit: int = 5,
    ) -> SearchMediaResult:
        store = VectorStore(ctx.deps.rag_dir / "chunks.parquet")
        results = query_media(
            query=query,
            client=ctx.deps.batch_client,
            store=store,
            media_types=media_types,
            top_k=limit,
            min_similarity=0.7,
            embedding_model=ctx.deps.embedding_model,
            output_dimensionality=ctx.deps.embedding_output_dimensionality,
            retrieval_mode=ctx.deps.retrieval_mode,
            retrieval_nprobe=ctx.deps.retrieval_nprobe,
            retrieval_overfetch=ctx.deps.retrieval_overfetch,
        )

        # Use Ibis streaming instead of pandas .execute().iterrows()
        # This avoids materializing the full result set and complies with Ibis-first policy
        items: list[MediaItem] = []
        for batch in stream_ibis(results, store._client, batch_size=100):
            items.extend(
                MediaItem(
                    media_type=row.get("media_type"),
                    media_path=row.get("media_path"),
                    original_filename=row.get("original_filename"),
                    description=(str(row.get("content", "")) or "")[:500],
                    similarity=float(row.get("similarity")) if row.get("similarity") is not None else None,
                )
                for row in batch
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
        if ctx.deps.annotations_store is None:
            raise RuntimeError("Annotation store is not configured")
        annotation = ctx.deps.annotations_store.save_annotation(
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
            output_dir=ctx.deps.output_dir,
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
    client: Any,
    embedding_model: str,
    embedding_output_dimensionality: int,
    retrieval_mode: str,
    retrieval_nprobe: int | None,
    retrieval_overfetch: int | None,
    annotations_store: AnnotationStore | None,
    agent_model: Any | None = None,
    register_tools: bool = True,
) -> tuple[list[str], list[str]]:
    """
    Execute the writer flow using Pydantic-AI agent tooling.

    Returns:
        Tuple (saved_posts, saved_profiles, freeform_content_path)
    """
    logger.info("Running writer via Pydantic-AI backend")
    if register_tools:
        agent = Agent[WriterAgentState, WriterAgentReturn](
            model=agent_model or GeminiModel(model_name),
            deps_type=WriterAgentState,
            output_type=WriterAgentReturn,
        )
        _register_writer_tools(agent)
    else:
        agent = Agent[WriterAgentState, str](
            model=agent_model or GeminiModel(model_name),
            deps_type=WriterAgentState,
        )

    state = WriterAgentState(
        period_date=period_date,
        output_dir=output_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        batch_client=client,
        embedding_model=embedding_model,
        embedding_output_dimensionality=embedding_output_dimensionality,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        annotations_store=annotations_store,
    )

    try:
        with logfire_span("writer_agent", period=period_date, model=model_name):
            result = agent.run_sync(prompt, deps=state)
            result_payload = getattr(result, "data", result)

            # Log completion metrics
            usage = result.usage()
            logfire_info(
                "Writer agent completed",
                period=period_date,
                posts_created=len(state.saved_posts),
                profiles_updated=len(state.saved_profiles),
                tokens_total=usage.total_tokens if usage else 0,
                tokens_input=usage.input_tokens if usage else 0,
                tokens_output=usage.output_tokens if usage else 0,
            )

            logger.info("Writer agent finished with summary: %s", getattr(result_payload, "summary", None))

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
        raise RuntimeError("Writer agent execution failed") from exc

    return state.saved_posts, state.saved_profiles


class WriterStreamResult:
    """Result from streaming writer agent.

    This class is an async context manager that properly wraps pydantic-ai's
    run_stream() async context manager and adds logfire observability spans.

    Usage:
        >>> async with write_posts_with_pydantic_agent_stream(...) as result:
        ...     async for chunk in result.stream_text():
        ...         print(chunk, end='', flush=True)
        ...     posts, profiles = await result.get_posts()
    """

    def __init__(
        self,
        agent: Any,
        prompt: str,
        state: WriterAgentState,
        period_date: str,
        model_name: str,
    ):
        self.agent = agent
        self.prompt = prompt
        self.state = state
        self.period_date = period_date
        self.model_name = model_name
        self._stream_context = None
        self._response = None
        self._span = None

    async def __aenter__(self):
        """Enter async context - start logfire span and pydantic-ai stream."""
        # Start logfire span
        self._span = logfire_span("writer_agent_stream", period=self.period_date, model=self.model_name)
        self._span.__enter__()

        # Start pydantic-ai stream (must use async with)
        self._stream_context = self.agent.run_stream(self.prompt, deps=self.state)
        self._response = await self._stream_context.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context - close stream and span."""
        try:
            if self._stream_context:
                await self._stream_context.__aexit__(exc_type, exc_val, exc_tb)
        finally:
            if self._span:
                self._span.__exit__(exc_type, exc_val, exc_tb)
        return False

    async def stream_text(self):
        """Stream text chunks from the agent."""
        if not self._response:
            raise RuntimeError(
                "WriterStreamResult must be used as async context manager "
                "(use: async with write_posts_with_pydantic_agent_stream(...) as result)"
            )
        async for chunk in self._response.stream_text():
            yield chunk

    async def get_posts(self) -> tuple[list[str], list[str]]:
        """Get final posts and profiles after streaming completes.

        Note: The state is populated during tool execution while streaming,
        so we can return it directly without waiting for additional data.
        """
        if not self._response:
            raise RuntimeError(
                "WriterStreamResult must be used as async context manager "
                "(use: async with write_posts_with_pydantic_agent_stream(...) as result)"
            )
        return self.state.saved_posts, self.state.saved_profiles


async def write_posts_with_pydantic_agent_stream(  # noqa: PLR0913
    *,
    prompt: str,
    model_name: str,
    period_date: str,
    output_dir: Path,
    profiles_dir: Path,
    rag_dir: Path,
    client: Any,
    embedding_model: str,
    embedding_output_dimensionality: int,
    retrieval_mode: str,
    retrieval_nprobe: int | None,
    retrieval_overfetch: int | None,
    annotations_store: AnnotationStore | None,
    agent_model: Any | None = None,
    register_tools: bool = True,
) -> WriterStreamResult:
    """
    Execute the writer flow using Pydantic-AI agent with streaming.

    This is an async version that streams agent responses token-by-token.
    Useful for interactive CLI tools and real-time progress updates.

    IMPORTANT: The returned WriterStreamResult is an async context manager
    and MUST be used with `async with`:

        async with write_posts_with_pydantic_agent_stream(...) as result:
            async for chunk in result.stream_text():
                print(chunk, end='', flush=True)
            posts, profiles = await result.get_posts()

    Args:
        (same as write_posts_with_pydantic_agent)

    Returns:
        WriterStreamResult async context manager for streaming and results
    """
    logger.info("Running writer via Pydantic-AI backend (streaming)")

    if register_tools:
        agent = Agent[WriterAgentState, WriterAgentReturn](
            model=agent_model or GeminiModel(model_name),
            deps_type=WriterAgentState,
            output_type=WriterAgentReturn,
        )
        _register_writer_tools(agent)
    else:
        agent = Agent[WriterAgentState, str](
            model=agent_model or GeminiModel(model_name),
            deps_type=WriterAgentState,
        )

    state = WriterAgentState(
        period_date=period_date,
        output_dir=output_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        batch_client=client,
        embedding_model=embedding_model,
        embedding_output_dimensionality=embedding_output_dimensionality,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        annotations_store=annotations_store,
    )

    # Return the context manager - caller must use `async with`
    return WriterStreamResult(agent, prompt, state, period_date, model_name)
