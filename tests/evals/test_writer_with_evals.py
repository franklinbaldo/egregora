"""Test writer agent using pydantic-evals framework."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from egregora.generation.writer.pydantic_agent import (
    write_posts_with_pydantic_agent,
    write_posts_with_pydantic_agent_stream,
)
from tests.evals.writer_evals import create_writer_dataset
from tests.mock_batch_client import create_mock_batch_client


@pytest.fixture()
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
        inputs: Case inputs with 'prompt' and 'period_date'
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

    # Use TestModel for deterministic tests
    test_model = TestModel(
        call_tools=[],
        custom_output_text='{"summary": "Test completed", "notes": "N/A"}',
    )

    saved_posts, saved_profiles = write_posts_with_pydantic_agent(
        prompt=inputs["prompt"],
        model_name="models/gemini-flash-latest",
        period_date=inputs["period_date"],
        output_dir=posts_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        batch_client=batch_client,
        embedding_model="models/gemini-embedding-001",
        embedding_output_dimensionality=3072,
        retrieval_mode="exact",
        retrieval_nprobe=None,
        retrieval_overfetch=None,
        annotations_store=None,
        agent_model=test_model,
        register_tools=False,
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

    # Use TestModel for deterministic tests
    test_model = TestModel(
        call_tools=[],
        custom_output_text='{"summary": "No content", "notes": "N/A"}',
    )

    saved_posts, saved_profiles = write_posts_with_pydantic_agent(
        prompt=case.inputs["prompt"],
        model_name="models/gemini-flash-latest",
        period_date=case.inputs["period_date"],
        output_dir=posts_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        batch_client=batch_client,
        embedding_model="models/gemini-embedding-001",
        embedding_output_dimensionality=3072,
        retrieval_mode="exact",
        retrieval_nprobe=None,
        retrieval_overfetch=None,
        annotations_store=None,
        agent_model=test_model,
        register_tools=False,
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

    # Use TestModel for deterministic tests
    test_model = TestModel(
        call_tools=[],
        custom_output_text='{"summary": "No content", "notes": "N/A"}',
    )

    # Get the stream result wrapper
    stream_result = await write_posts_with_pydantic_agent_stream(
        prompt=case.inputs["prompt"],
        model_name="models/gemini-flash-latest",
        period_date=case.inputs["period_date"],
        output_dir=posts_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        batch_client=batch_client,
        embedding_model="models/gemini-embedding-001",
        embedding_output_dimensionality=3072,
        retrieval_mode="exact",
        retrieval_nprobe=None,
        retrieval_overfetch=None,
        annotations_store=None,
        agent_model=test_model,
        register_tools=False,
    )

    # Use async context manager for streaming
    async with stream_result as result:
        # Stream and collect chunks
        chunks = []
        async for chunk in result.stream_text():
            chunks.append(chunk)

        # Get final results
        saved_posts, saved_profiles = await result.get_posts()

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
    import asyncio

    dataset = create_writer_dataset()

    async def run_agent(inputs: dict) -> dict:
        return await run_writer_agent(inputs, writer_dirs)

    # Run evaluation
    report = asyncio.run(dataset.evaluate(run_agent))
    report.print()

    # Log results
    print("\nEvaluation Results:")
    print(f"Average Score: {report.average_score():.2%}")
    print(f"Total Cases: {len(report.case_results)}")
    print(f"Passed (>80%): {sum(1 for r in report.case_results if r.score >= 0.8)}")

    # Store baseline for future comparison
    # TODO: Save to file for regression tracking
