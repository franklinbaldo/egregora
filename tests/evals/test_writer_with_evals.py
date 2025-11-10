"""Test writer agent using pydantic-evals framework."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic_ai.models.test import TestModel

from egregora.agents.shared.rag import VectorStore
from egregora.agents.writer.agent import (
    WriterRuntimeContext,
    write_posts_with_pydantic_agent,
    write_posts_with_pydantic_agent_stream,
)
from egregora.config.loader import create_default_config
from tests.helpers.storage import InMemoryJournalStorage, InMemoryPostStorage, InMemoryProfileStorage
from tests.evals.writer_evals import create_writer_dataset
from tests.utils.mock_batch_client import create_mock_batch_client


@pytest.fixture
def writer_dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create temporary directories for writer tests."""
    site_dir = tmp_path / "site" / "docs"
    posts_dir = site_dir / "posts"
    profiles_dir = site_dir / "profiles"
    rag_dir = site_dir / "rag"
    posts_dir.mkdir(parents=True)
    profiles_dir.mkdir()
    rag_dir.mkdir()
    return posts_dir, profiles_dir, rag_dir


async def run_writer_agent(inputs: dict, writer_dirs: tuple[Path, Path, Path]) -> dict:
    """Run writer agent and return structured output.

    Args:
        inputs: Case inputs with 'prompt' and 'window_id'
        writer_dirs: Tuple of (posts_dir, profiles_dir, rag_dir)

    Returns:
        dict with:
        - posts_created: int
        - summary: str
        - has_title: bool (if posts created)
        - has_tags: bool (if posts created)

    """
    posts_dir, profiles_dir, rag_dir = writer_dirs
    batch_client = create_mock_batch_client()

    # MODERN (Phase 2): Create config and context
    site_root = posts_dir.parent.parent  # Go up from docs/posts to site root
    config = create_default_config(site_root)
    config = config.model_copy(
        deep=True,
        update={
            "rag": config.rag.model_copy(update={"mode": "exact"}),
        },
    )

    # Parse window_id string (e.g., "2025-01-01") to start_time/end_time
    window_date = datetime.fromisoformat(inputs["window_id"]).date()
    start_time = datetime.combine(window_date, datetime.min.time(), tzinfo=ZoneInfo("UTC"))
    end_time = datetime.combine(window_date, datetime.max.time(), tzinfo=ZoneInfo("UTC"))

    # MODERN (Adapter Pattern): Use in-memory storage for testing
    posts_storage = InMemoryPostStorage()
    profiles_storage = InMemoryProfileStorage()
    journals_storage = InMemoryJournalStorage()
    rag_store = VectorStore(rag_dir / "chunks.parquet")

    context = WriterRuntimeContext(
        start_time=start_time,
        end_time=end_time,
        # Storage protocols (in-memory for testing)
        posts=posts_storage,
        profiles=profiles_storage,
        journals=journals_storage,
        # Pre-constructed stores
        rag_store=rag_store,
        annotations_store=None,
        # LLM client
        client=batch_client,
        # Prompt templates directory
        prompts_dir=None,
        # Deprecated (kept for backward compatibility)
        output_dir=posts_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        site_root=site_root,
    )

    # Use TestModel for deterministic tests
    test_model = TestModel(
        call_tools=[],
        custom_output_text='{"summary": "Test completed", "notes": "N/A"}',
    )

    saved_posts, _saved_profiles = write_posts_with_pydantic_agent(
        prompt=inputs["prompt"],
        config=config,
        context=context,
        test_model=test_model,
    )

    # Analyze created posts
    result = {
        "posts_created": len(saved_posts),
        "summary": "Test completed",
    }

    if saved_posts:
        # Check first post for metadata
        first_post = Path(saved_posts[0])
        if first_post.exists():
            content = first_post.read_text()
            result["has_title"] = "title:" in content.lower()
            result["has_tags"] = "tags:" in content.lower()

    return result


def test_writer_evaluation_empty_conversation(writer_dirs):
    """Test writer correctly handles empty conversation."""
    # Use synchronous version instead of async
    posts_dir, profiles_dir, rag_dir = writer_dirs
    batch_client = create_mock_batch_client()

    dataset = create_writer_dataset()
    case = next(c for c in dataset.cases if c.name == "empty_conversation")

    # MODERN (Phase 2): Create config and context
    site_root = posts_dir.parent.parent  # Go up from docs/posts to site root
    config = create_default_config(site_root)
    config = config.model_copy(
        deep=True,
        update={
            "rag": config.rag.model_copy(update={"mode": "exact"}),
        },
    )

    # Parse window_id string (e.g., "2025-01-01") to start_time/end_time
    window_date = datetime.fromisoformat(case.inputs["window_id"]).date()
    start_time = datetime.combine(window_date, datetime.min.time(), tzinfo=ZoneInfo("UTC"))
    end_time = datetime.combine(window_date, datetime.max.time(), tzinfo=ZoneInfo("UTC"))

    # MODERN (Adapter Pattern): Use in-memory storage for testing
    posts_storage = InMemoryPostStorage()
    profiles_storage = InMemoryProfileStorage()
    journals_storage = InMemoryJournalStorage()
    rag_store = VectorStore(rag_dir / "chunks.parquet")

    context = WriterRuntimeContext(
        start_time=start_time,
        end_time=end_time,
        # Storage protocols (in-memory for testing)
        posts=posts_storage,
        profiles=profiles_storage,
        journals=journals_storage,
        # Pre-constructed stores
        rag_store=rag_store,
        annotations_store=None,
        # LLM client
        client=batch_client,
        # Prompt templates directory
        prompts_dir=None,
        # Deprecated (kept for backward compatibility)
        output_dir=posts_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        site_root=site_root,
    )

    # Use TestModel for deterministic tests
    test_model = TestModel(
        call_tools=[],
        custom_output_text='{"summary": "No content", "notes": "N/A"}',
    )

    saved_posts, _saved_profiles = write_posts_with_pydantic_agent(
        prompt=case.inputs["prompt"],
        config=config,
        context=context,
        test_model=test_model,
    )

    # Should create no posts
    assert len(saved_posts) == 0


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_writer_stream_empty_conversation(writer_dirs):
    """Test streaming writer correctly handles empty conversation."""
    posts_dir, profiles_dir, rag_dir = writer_dirs
    batch_client = create_mock_batch_client()

    dataset = create_writer_dataset()
    case = next(c for c in dataset.cases if c.name == "empty_conversation")

    # MODERN (Phase 2): Create config and context
    site_root = posts_dir.parent.parent  # Go up from docs/posts to site root
    config = create_default_config(site_root)
    config = config.model_copy(
        deep=True,
        update={
            "rag": config.rag.model_copy(update={"mode": "exact"}),
        },
    )

    # Parse window_id string (e.g., "2025-01-01") to start_time/end_time
    window_date = datetime.fromisoformat(case.inputs["window_id"]).date()
    start_time = datetime.combine(window_date, datetime.min.time(), tzinfo=ZoneInfo("UTC"))
    end_time = datetime.combine(window_date, datetime.max.time(), tzinfo=ZoneInfo("UTC"))

    # MODERN (Adapter Pattern): Use in-memory storage for testing
    posts_storage = InMemoryPostStorage()
    profiles_storage = InMemoryProfileStorage()
    journals_storage = InMemoryJournalStorage()
    rag_store = VectorStore(rag_dir / "chunks.parquet")

    context = WriterRuntimeContext(
        start_time=start_time,
        end_time=end_time,
        # Storage protocols (in-memory for testing)
        posts=posts_storage,
        profiles=profiles_storage,
        journals=journals_storage,
        # Pre-constructed stores
        rag_store=rag_store,
        annotations_store=None,
        # LLM client
        client=batch_client,
        # Prompt templates directory
        prompts_dir=None,
        # Deprecated (kept for backward compatibility)
        output_dir=posts_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        site_root=site_root,
    )

    # Use TestModel for deterministic tests
    test_model = TestModel(
        call_tools=[],
        custom_output_text='{"summary": "No content", "notes": "N/A"}',
    )

    # Get the stream result wrapper
    stream_result = await write_posts_with_pydantic_agent_stream(
        prompt=case.inputs["prompt"],
        config=config,
        context=context,
        test_model=test_model,
    )

    # Use async context manager for streaming
    async with stream_result as result:
        # Stream and collect chunks
        chunks = [chunk async for chunk in result.stream()]

        # Get final results
        saved_posts, _saved_profiles = result.get_output_paths()

    # Should create no posts
    assert len(saved_posts) == 0
    # Should have streamed some text (the summary)
    assert len(chunks) > 0


def test_writer_evaluation_with_dataset(writer_dirs):
    """Run full evaluation dataset against writer agent.

    This is a placeholder for when we implement live evaluation.
    Currently just validates the dataset structure.
    """
    dataset = create_writer_dataset()

    # Verify dataset is properly structured
    assert len(dataset.cases) >= 5
    assert all(c.inputs is not None for c in dataset.cases)
    assert len(dataset.evaluators) > 0

    # TODO: Uncomment when ready for full evaluation
    # async def run_agent(inputs: dict) -> dict:
    #     return await run_writer_agent(inputs, writer_dirs)
    #
    # report = await dataset.evaluate(run_agent)
    # report.print()
    #
    # # Check baseline scores
    # assert report.average_score() > 0.5  # Initial baseline


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_EVALS") != "1",
    reason="Live evaluations only run with RUN_LIVE_EVALS=1",
)
def test_writer_live_evaluation(writer_dirs):
    """Run live evaluation with real model (requires API key and RUN_LIVE_EVALS=1).

    This test is skipped by default. Run with:
        RUN_LIVE_EVALS=1 pytest tests/evals/test_writer_with_evals.py::test_writer_live_evaluation
    """
    import asyncio  # noqa: PLC0415 - only needed for this async test

    dataset = create_writer_dataset()

    async def run_agent(inputs: dict) -> dict:
        return await run_writer_agent(inputs, writer_dirs)

    # Run evaluation
    report = asyncio.run(dataset.evaluate(run_agent))
    report.print()

    # Log results

    # Store baseline for future comparison
    # TODO: Save to file for regression tracking
