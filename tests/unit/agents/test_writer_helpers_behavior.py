"""Behavioral tests for writer agent helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel
from pydantic_ai import ModelRetry

from egregora.agents.writer_helpers import (
    PromptTooLargeError,
    build_rag_context_for_prompt,
    load_profiles_context,
    process_tool_result,
    register_writer_tools,
    validate_prompt_fits,
)
from egregora.data_primitives.document import Document, DocumentType
from egregora.output_sinks.exceptions import DocumentNotFoundError

# ==============================================================================
# process_tool_result
# ==============================================================================


class DummyModel(BaseModel):
    key: str


def test_process_tool_result_behavior():
    """
    Given various input types
    When process_tool_result is called
    Then it should return a dictionary or None appropriately.
    """
    # Valid JSON
    assert process_tool_result('{"a": 1}') == {"a": 1}

    # Invalid JSON
    assert process_tool_result("{invalid") is None

    # Pydantic Model
    model = DummyModel(key="value")
    assert process_tool_result(model) == {"key": "value"}

    # Dict
    assert process_tool_result({"x": 1}) == {"x": 1}

    # None/Other
    assert process_tool_result(None) is None
    assert process_tool_result(123) is None


# ==============================================================================
# validate_prompt_fits
# ==============================================================================


def test_validate_prompt_fits_behavior():
    """
    Given a prompt and configuration
    When validate_prompt_fits is called
    Then it should check limits and use appropriate counters.
    """
    config = MagicMock()
    config.pipeline.max_prompt_tokens = 100
    config.pipeline.use_full_context_window = False

    # Case 1: Within limit (fallback counting: 20 chars / 4 = 5 tokens)
    prompt = "x" * 20
    count = validate_prompt_fits(prompt, "model", config, "window")
    assert count == 5

    # Case 2: Exceeds limit
    prompt = "x" * 404  # ~101 tokens
    with pytest.raises(PromptTooLargeError):
        validate_prompt_fits(prompt, "model", config, "window")

    # Case 3: Exceeds limit but allowed via config
    config.pipeline.use_full_context_window = True
    count = validate_prompt_fits(prompt, "model", config, "window")
    assert count == 101


def test_validate_prompt_fits_native_counter():
    """
    Given a model with native counting
    When validate_prompt_fits is called
    Then it should use the native counter.
    """
    config = MagicMock()
    config.pipeline.max_prompt_tokens = 100
    config.pipeline.use_full_context_window = False

    model_instance = MagicMock()
    # Mock async count_tokens
    model_instance.count_tokens = AsyncMock(return_value=50)

    prompt = "short"
    count = validate_prompt_fits(prompt, "model", config, "window", model_instance=model_instance)

    assert count == 50
    model_instance.count_tokens.assert_called_once_with(prompt)


# ==============================================================================
# build_rag_context_for_prompt
# ==============================================================================


@patch("egregora.agents.writer_helpers.search")
@patch("egregora.agents.writer_helpers.reset_backend")
def test_build_rag_context_behavior(_, mock_search):
    """
    Given RAG hits
    When build_rag_context_for_prompt is called
    Then it should format the context correctly.
    """
    # Mock RAG response
    hit = MagicMock()
    hit.score = 0.85
    hit.metadata = {"title": "Test Post", "slug": "test-post", "date": "2023-01-01"}
    hit.text = "Relevant content"

    mock_search.return_value.hits = [hit]

    cache = MagicMock()
    # Ensure cache miss first
    cache.rag.get.side_effect = KeyError

    result = build_rag_context_for_prompt("query", top_k=1, cache=cache)

    assert "## Similar Posts" in result
    assert "Test Post" in result
    assert "posts/2023/01/01/test-post/" in result
    assert "(similarity: 85%)" in result
    assert "Relevant content" in result

    # Verify caching
    cache.rag.set.assert_called_once()


@patch("egregora.agents.writer_helpers.search")
@patch("egregora.agents.writer_helpers.reset_backend")
def test_build_rag_context_empty_and_errors(_, mock_search):
    """
    Given no hits or backend errors
    When build_rag_context_for_prompt is called
    Then it should return empty string.
    """
    # Empty query
    assert build_rag_context_for_prompt("") == ""

    # No hits
    mock_search.return_value.hits = []
    assert build_rag_context_for_prompt("query") == ""

    # Backend error
    mock_search.side_effect = ConnectionError
    assert build_rag_context_for_prompt("query") == ""


# ==============================================================================
# load_profiles_context
# ==============================================================================


def test_load_profiles_context_behavior():
    """
    Given a list of authors
    When load_profiles_context is called
    Then it should retrieve profiles from output sink.
    """
    output_sink = MagicMock()

    # Case 1: Found
    doc = Document(id="a1", content="Profile Content", type=DocumentType.PROFILE, metadata={})
    output_sink.get.return_value = doc

    result = load_profiles_context(["author1"], output_sink)
    assert "Active Participants" in result
    assert "Profile Content" in result

    # Case 2: Not Found
    output_sink.get.side_effect = DocumentNotFoundError("profile", "author2")
    result = load_profiles_context(["author2"], output_sink)
    assert "(No profile yet - first appearance)" in result


# ==============================================================================
# register_writer_tools (Validation Logic)
# ==============================================================================


@patch("egregora.agents.writer_helpers.write_post_impl")
def test_write_post_tool_validation(mock_impl):
    """
    Given the write_post_tool
    When called with various inputs
    Then it should validate metadata correctly.
    """
    # Capture the tool
    agent = MagicMock()
    captured_tools = {}

    def capture(func):
        captured_tools[func.__name__] = func
        return func

    agent.tool.side_effect = capture
    config = MagicMock()
    config.rag.enabled = False

    # Mock banner generation availability to avoid import side effects if possible
    # But since we import is_banner_generation_available, we might need to patch it if it does IO.
    # For now assuming it's safe or we patch it.
    with patch("egregora.agents.writer_helpers.is_banner_generation_available", return_value=False):
        register_writer_tools(agent, config)

    write_tool = captured_tools["write_post_tool"]

    # Mock Context
    ctx = MagicMock()
    ctx.deps.model_name = "test-model"

    # Case 1: Missing Title
    with pytest.raises(ModelRetry) as exc:
        write_tool(ctx, {"tags": ["t"]}, "content")
    assert "Missing required metadata fields" in str(exc.value)

    # Case 2: Missing Tags
    with pytest.raises(ModelRetry) as exc:
        write_tool(ctx, {"title": "t"}, "content")
    assert "tags" in str(exc.value)

    # Case 3: String Metadata (Valid)
    mock_impl.return_value = MagicMock(status="success")
    valid_json = '{"title": "T", "tags": ["t"], "slug": "s"}'
    write_tool(ctx, valid_json, "content")

    # Check that impl was called with parsed dict
    args, _ = mock_impl.call_args
    meta_arg = args[1]
    assert meta_arg["title"] == "T"
    assert meta_arg["tags"] == ["t"]
    assert "model" in meta_arg
    assert "id" in meta_arg  # Generated
    assert "updated" in meta_arg  # Generated

    # Case 4: Date Parsing
    write_tool(ctx, {"title": "T", "tags": ["t"], "date": "2023-01-01"}, "content")
    args, _ = mock_impl.call_args
    meta_arg = args[1]
    assert "2023-01-01" in meta_arg["updated"]
