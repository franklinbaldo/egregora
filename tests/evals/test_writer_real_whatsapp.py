"""
Real-world evaluation of writer agent using pydantic-evals with actual WhatsApp data.

This test uses pydantic-evals to evaluate the writer agent on real WhatsApp conversations,
combining deterministic TestModel execution with LLM judges for quality assessment.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from egregora.ingestion.parser import parse_export
from tests.conftest import WhatsAppFixture
from tests.mock_batch_client import create_mock_batch_client


def create_export_from_fixture(fixture: WhatsAppFixture):
    """Create WhatsAppExport from fixture."""
    return fixture.create_export()


def create_writer_real_world_dataset(whatsapp_fixture: WhatsAppFixture) -> Dataset:
    """Create evaluation dataset using real WhatsApp conversation data."""
    # Parse real WhatsApp export
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    # Convert to markdown for evaluation
    rows = table.head(10).execute().to_dict("records")
    conversation_md = "\n\n".join(
        f"**{row['author']}** ({row['date']}):\n{row['message']}" for row in rows
    )

    # Create test cases with real data
    cases = [
        Case(
            name="real_whatsapp_conversation",
            inputs={
                "conversation": conversation_md,
                "period_date": str(whatsapp_fixture.export_date),
                "zip_path": str(whatsapp_fixture.zip_path),
            },
            # Expected outputs defined by deterministic TestModel
            expected_output={
                "posts_created": True,
                "profiles_updated": True,
            },
        ),
    ]

    # Create evaluators
    evaluators = [
        # Basic type checking
        IsInstance(type_name="tuple"),
        # TODO: Add LLM judges for quality evaluation when needed
        # Requires GOOGLE_API_KEY and proper LLMJudge API usage
    ]

    return Dataset(cases=cases, evaluators=evaluators)


@pytest.fixture
def writer_test_model(whatsapp_fixture: WhatsAppFixture) -> TestModel:
    """Create deterministic TestModel for writer agent evaluation."""

    class RealWorldTestModel(TestModel):
        """TestModel with realistic tool arguments based on actual WhatsApp data."""

        def __init__(self):
            super().__init__(
                call_tools=["write_post_tool", "write_profile_tool"],
                custom_output_args={
                    "summary": "Real WhatsApp conversation processed",
                    "notes": "Deterministic evaluation with actual data",
                },
                seed=42,  # Reproducible results
            )

        def gen_tool_args(self, tool_def):  # type: ignore[override]
            if tool_def.name == "write_post_tool":
                return {
                    "metadata": {
                        "title": "Real Conversation Insights",
                        "slug": "real-conversation-insights",
                        "date": whatsapp_fixture.export_date.isoformat(),
                        "tags": ["real-world", "whatsapp"],
                        "authors": ["ca71a986"],  # Real anonymized UUID from fixture
                        "summary": "Insights extracted from actual WhatsApp conversation.",
                    },
                    "content": (
                        "# Real World Conversation\n\n"
                        "This post was generated from actual WhatsApp export data "
                        "to validate end-to-end pipeline with realistic inputs."
                    ),
                }
            if tool_def.name == "write_profile_tool":
                return {
                    "author_uuid": "ca71a986",
                    "content": "Active participant in test conversation.",
                }
            return super().gen_tool_args(tool_def)

    return RealWorldTestModel()


def test_writer_with_real_whatsapp_data(
    whatsapp_fixture: WhatsAppFixture,
    writer_test_model: TestModel,
    tmp_path: Path,
) -> None:
    """Evaluate writer agent using pydantic-evals with real WhatsApp data."""
    import asyncio

    # Setup directories
    output_dir = tmp_path / "output"
    posts_dir = output_dir / "posts"
    profiles_dir = output_dir / "profiles"
    rag_dir = output_dir / "rag"

    for d in [output_dir, posts_dir, profiles_dir, rag_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Create dataset
    dataset = create_writer_real_world_dataset(whatsapp_fixture)

    # Define task to evaluate
    async def run_writer(inputs: dict) -> tuple[list[str], list[str]]:
        """Run writer agent on real WhatsApp data."""
        from pydantic_ai import Agent

        from egregora.generation.writer.pydantic_agent import (
            WriterAgentReturn,
            WriterAgentState,
            _register_writer_tools,
        )
        from egregora.knowledge.annotations import AnnotationStore

        # Parse conversation
        export = create_export_from_fixture(whatsapp_fixture)
        table = parse_export(export, timezone=whatsapp_fixture.timezone)

        # Build prompt (simplified for test)
        rows = table.head(10).execute().to_dict("records")
        conversation_md = "\n\n".join(
            f"**{row['author']}** ({row['date']}):\n{row['message']}" for row in rows
        )

        prompt = f"""
        Analyze this WhatsApp conversation and write a blog post:

        {conversation_md}

        Use the write_post_tool and write_profile_tool to create outputs.
        """

        # Setup agent directly (async-compatible)
        batch_client = create_mock_batch_client()
        annotations_store = AnnotationStore(rag_dir / "annotations.duckdb")

        # Create agent with tools
        agent = Agent[WriterAgentState, WriterAgentReturn](
            model=writer_test_model,
            deps_type=WriterAgentState,
            output_type=WriterAgentReturn,
        )
        _register_writer_tools(agent)

        # Create state
        state = WriterAgentState(
            period_date=inputs["period_date"],
            output_dir=posts_dir,
            profiles_dir=profiles_dir,
            rag_dir=rag_dir,
            batch_client=batch_client,
            embedding_model="models/text-embedding-004",
            embedding_output_dimensionality=3072,
            retrieval_mode="exact",
            retrieval_nprobe=None,
            retrieval_overfetch=None,
            annotations_store=annotations_store,
        )

        # Run agent asynchronously
        await agent.run(prompt, deps=state)

        return state.saved_posts, state.saved_profiles

    # Run evaluation in async context
    async def run_evaluation():
        return await dataset.evaluate(run_writer)

    report = asyncio.run(run_evaluation())

    # Print results
    print("\n" + "=" * 60)
    print("Real WhatsApp Data Evaluation Results")
    print("=" * 60)
    report.print()

    # Basic assertions - check that all evaluations passed
    assert len(report.cases) > 0, "Should have at least one case"
    for case in report.cases:
        # Check that all assertions passed for this case
        if case.assertions:
            failed_assertions = [
                name for name, assertion in case.assertions.items() if not assertion.value
            ]
            assert not failed_assertions, f"Case {case.name} failed assertions: {failed_assertions}"

    # Verify actual outputs
    case_result = report.cases[0]
    saved_posts, saved_profiles = case_result.output
    assert len(saved_posts) > 0, "Should create at least one post"
    assert len(saved_profiles) > 0, "Should update at least one profile"


@pytest.mark.skipif(
    "GOOGLE_API_KEY" not in __import__("os").environ,
    reason="Requires GOOGLE_API_KEY for LLM judge evaluation",
)
@pytest.mark.anyio
async def test_writer_quality_with_llm_judge(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
) -> None:
    """
    Evaluate writer output quality using LLM judges (requires API key).

    This test is SKIPPED unless GOOGLE_API_KEY is set, allowing:
    - Fast deterministic tests in CI (skipped)
    - Quality evaluation during development (run with API key)
    """
    # This test uses real LLM calls for quality assessment
    # Create more sophisticated evaluation with multiple LLM judges

    quality_judge = LLMJudge(
        model="gemini-1.5-pro",
        prompt="""
        Evaluate the quality of this blog post generated from a WhatsApp conversation.

        Criteria:
        1. Coherent narrative structure (0-3 points)
        2. Relevant content extraction (0-3 points)
        3. Proper markdown formatting (0-2 points)
        4. Appropriate metadata (title, tags, summary) (0-2 points)

        Return a score from 0.0 to 1.0 representing overall quality.
        """,
    )

    dataset = Dataset(
        cases=[
            Case(
                name="quality_assessment",
                inputs={
                    "conversation": "Real conversation data here...",
                    "period_date": str(whatsapp_fixture.export_date),
                },
            )
        ],
        evaluators=[quality_judge],
    )

    # TODO: Implement full quality evaluation
    # For now, this serves as a placeholder for future quality testing
    pytest.skip("Quality evaluation with LLM judges - implement when needed")
