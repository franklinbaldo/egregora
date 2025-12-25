from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock

import pytest

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Document, DocumentType
from egregora_v3.engine.tools import (
    count_documents_by_type,
    get_document_by_id,
    get_pipeline_metadata,
    get_recent_posts,
    search_prior_work,
)


@pytest.fixture
def mock_context() -> PipelineContext:
    """Provides a mocked PipelineContext for tool tests."""
    mock_library = MagicMock()
    mock_library.posts = MagicMock()
    mock_library.get = MagicMock()
    mock_library.count = MagicMock()

    context = MagicMock(spec=PipelineContext)
    context.library = mock_library
    context.run_id = "test-run-123"
    context.metadata = {"extra": "data"}
    return context


@pytest.mark.asyncio
async def test_get_recent_posts_delegates_sorting_and_limiting_to_repository(
    mock_context: PipelineContext,
):
    """Tests that get_recent_posts uses repository for sorting and limiting."""
    limit = 7
    await get_recent_posts(mock_context, limit=limit)
    mock_context.library.posts.list.assert_called_once_with(
        doc_type=DocumentType.POST, order_by="updated", limit=limit
    )


@pytest.mark.asyncio
async def test_search_prior_work_placeholder(mock_context: PipelineContext):
    """Tests the placeholder implementation of search_prior_work."""
    result = await search_prior_work(mock_context, "test query")
    assert result == []


@pytest.mark.asyncio
async def test_get_document_by_id(mock_context: PipelineContext):
    """Tests retrieving a document by its ID."""
    doc_id = "test-doc-id"
    expected_doc = Document(
        content="Test", doc_type=DocumentType.POST, title="Test"
    )
    mock_context.library.get.return_value = expected_doc

    result = await get_document_by_id(mock_context, doc_id)

    mock_context.library.get.assert_called_once_with(doc_id)
    assert result == expected_doc


@pytest.mark.asyncio
async def test_count_documents_by_type(mock_context: PipelineContext):
    """Tests counting documents of a specific type."""
    doc_type = DocumentType.POST
    expected_count = 42
    mock_context.library.count.return_value = expected_count

    result = await count_documents_by_type(mock_context, doc_type)

    mock_context.library.count.assert_called_once_with(doc_type)
    assert result == expected_count


@pytest.mark.asyncio
async def test_get_pipeline_metadata_uses_full_metadata_property(
    mock_context: PipelineContext,
):
    """Tests that get_pipeline_metadata uses the full_metadata property."""
    expected_metadata = {"run_id": "test-run-123", "extra": "data"}
    # Store the mock in a variable for later assertion
    prop_mock = PropertyMock(return_value=expected_metadata)
    type(mock_context).full_metadata = prop_mock

    result = await get_pipeline_metadata(mock_context)

    assert result == expected_metadata
    # Assert that the property was accessed once
    prop_mock.assert_called_once()
