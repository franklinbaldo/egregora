"""Tests for Pydantic AI editor agent."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from egregora.agents.editor.editor_agent import run_editor_session_with_pydantic_agent
from egregora.config import ModelConfig


@pytest.fixture
def test_post(tmp_path: Path) -> Path:
    """Create a test post file."""
    post_dir = tmp_path / "posts"
    post_dir.mkdir()
    post_path = post_dir / "test-post.md"
    post_path.write_text(
        """---
title: Test Post
date: 2025-01-15
tags: [test]
---

# Test Post

This is a test post for the editor agent.

## Section 1

Some content here.

## Section 2

More content here.
"""
    )
    return post_path


@pytest.fixture
def model_config() -> ModelConfig:
    """Create a test model configuration."""
    # ModelConfig uses site_config dict for model overrides
    site_config = {
        "writer_model": "models/gemini-flash-latest",
        "editor_model": "models/gemini-flash-latest",
        "embedding_model": "models/gemini-embedding-001",
        "embedding_output_dimensionality": 3072,
    }
    return ModelConfig(site_config=site_config)


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_editor_agent_with_test_model(test_post: Path, model_config: ModelConfig, tmp_path: Path):
    """Test editor agent with TestModel (no actual LLM calls)."""
    # Create RAG directory (even though it's empty)
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    # Use TestModel for deterministic testing
    test_model = TestModel(
        call_tools=[],  # No tool calls, just return result
        custom_output_args={
            "decision": "publish",
            "notes": "Test post looks good",
        },
    )

    # Mock client (won't be used with TestModel)
    from unittest.mock import Mock

    mock_client = Mock()

    # Run editor session
    result = await run_editor_session_with_pydantic_agent(
        post_path=test_post,
        client=mock_client,
        model_config=model_config,
        rag_dir=rag_dir,
        context={},
        max_turns=15,
        agent_model=test_model,
    )

    # Verify result structure
    assert "final_content" in result
    assert "decision" in result
    assert "notes" in result
    assert "edits_made" in result
    assert "tool_calls" in result

    # Verify decision
    assert result["decision"] == "publish"
    assert result["notes"] == "Test post looks good"
    assert result["edits_made"] is False  # No edits made


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_editor_agent_with_edit_tool(test_post: Path, model_config: ModelConfig, tmp_path: Path):
    """Test editor agent that calls edit_line tool."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    # TestModel that will call edit_line tool
    test_model = TestModel(
        call_tools=["edit_line_tool"],
        custom_output_args={
            "decision": "publish",
            "notes": "Made some edits",
        },
    )

    from unittest.mock import Mock

    mock_client = Mock()

    # Run editor session
    result = await run_editor_session_with_pydantic_agent(
        post_path=test_post,
        client=mock_client,
        model_config=model_config,
        rag_dir=rag_dir,
        context={},
        max_turns=15,
        agent_model=test_model,
    )

    # Verify result
    assert result["decision"] == "publish"
    assert result["notes"] == "Made some edits"
    # Note: edit_line will be called but with whatever args TestModel provides
    # The edit may or may not succeed depending on the args


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_editor_agent_hold_decision(test_post: Path, model_config: ModelConfig, tmp_path: Path):
    """Test editor agent with 'hold' decision."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    test_model = TestModel(
        call_tools=[],
        custom_output_args={
            "decision": "hold",
            "notes": "Needs human review",
        },
    )

    from unittest.mock import Mock

    mock_client = Mock()

    result = await run_editor_session_with_pydantic_agent(
        post_path=test_post,
        client=mock_client,
        model_config=model_config,
        rag_dir=rag_dir,
        context={},
        max_turns=15,
        agent_model=test_model,
    )

    assert result["decision"] == "hold"
    assert result["notes"] == "Needs human review"


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_editor_agent_nonexistent_post(model_config: ModelConfig, tmp_path: Path):
    """Test editor agent with nonexistent post file."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    nonexistent_post = tmp_path / "nonexistent.md"

    test_model = TestModel()
    from unittest.mock import Mock

    mock_client = Mock()

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        await run_editor_session_with_pydantic_agent(
            post_path=nonexistent_post,
            client=mock_client,
            model_config=model_config,
            rag_dir=rag_dir,
            context={},
            agent_model=test_model,
        )
