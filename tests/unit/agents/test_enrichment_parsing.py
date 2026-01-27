from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from egregora.agents.enricher import EnrichmentRuntimeContext, EnrichmentWorker
from egregora.agents.exceptions import EnrichmentParsingError


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=EnrichmentRuntimeContext)
    ctx.output_format = MagicMock()
    ctx.cache = MagicMock()
    ctx.library = None
    ctx.input_path = None
    return ctx


@pytest.fixture
def worker(mock_context):
    return EnrichmentWorker(ctx=mock_context)


def test_parse_media_result_constructs_markdown_with_slug_filename(worker):
    """
    Test that _parse_media_result uses the slug to construct the filename
    in the fallback markdown link, NOT the original filename.
    """
    # Input task
    original_filename = "IMG-2025-OLD.jpg"
    task = {
        "task_id": "task-1",
        "_parsed_payload": {"filename": original_filename},
    }

    # Helper result object
    # Mocking what comes from the KeyRotator/Gemini
    res = SimpleNamespace(
        tag="tag-1",
        error=None,
        response={
            "text": '{"slug": "cool-slug-name", "description": "A cool description.", "alt_text": "Alt text"}'
        },  # Mock Gemini response
    )

    # Executing the method under test
    # Note: _parse_media_result signature: (res, task) -> (payload, output)
    result = worker._parse_media_result(res, task)

    assert result is not None
    _payload, output = result

    # Assertions
    assert output.slug == "cool-slug-name"

    # The critical check: does the markdown use the NEW filename?
    # Expected filename: cool-slug-name.jpg (assuming .jpg from original)
    expected_filename = "cool-slug-name.jpg"

    assert f"({expected_filename})" in output.markdown, (
        f"Markdown should contain link to '{expected_filename}', but got:\n{output.markdown}"
    )

    assert f"({original_filename})" not in output.markdown, (
        "Markdown should NOT contain link to original filename"
    )

    # Verify Tags section exists (per user request)
    assert "## Tags" in output.markdown


def test_parse_media_result_handles_missing_slug(worker):
    """Test fallback when slug is missing/invalid."""
    task = {"task_id": "task-2", "_parsed_payload": {"filename": "IMG.jpg"}}

    # Empty JSON response -> no slug -> should raise EnrichmentParsingError
    SimpleNamespace(tag="t", error=None, response={"text": "{}"})

    # Should raise EnrichmentParsingError if slug is missing and no pre-existing markdown
    with pytest.raises(EnrichmentParsingError, match="Missing slug or markdown"):
        worker._parse_media_result(SimpleNamespace(tag="t", error=None, response={"text": "{}"}), task)
