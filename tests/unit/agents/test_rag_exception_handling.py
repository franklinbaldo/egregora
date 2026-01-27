"""Unit tests for RAG exception handling in the write pipeline."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from egregora.orchestration.pipelines.etl.preparation import (
    prepare_pipeline_data,
)


@pytest.fixture
def mock_pipeline_context():
    """Create a mock pipeline context."""
    ctx = MagicMock()
    ctx.config.rag.enabled = True
    ctx.output_format.documents.return_value = []
    # Mock output_sink since it's used in preparation
    ctx.output_sink = MagicMock()
    ctx.output_sink.documents.return_value = []
    return ctx


@pytest.fixture
def mock_adapter():
    """Create a mock adapter."""
    adapter = MagicMock()
    adapter.parse.return_value = MagicMock()  # messages_table
    return adapter


@pytest.fixture
def mock_run_params():
    """Create mock run parameters."""
    params = MagicMock()
    params.config.rag.enabled = True
    params.config.pipeline.timezone = "UTC"
    params.config.pipeline.step_size = 100
    params.config.pipeline.step_unit = "messages"
    params.config.pipeline.overlap_ratio = 0.0
    params.config.pipeline.max_window_time = None
    params.config.pipeline.from_date = None
    params.config.pipeline.to_date = None
    params.config.models.enricher_vision = "mock-vision-model"
    params.config.models.embedding = "mock-embedding-model"
    params.config.pipeline.checkpoint_enabled = False
    params.config.enrichment.enabled = True
    return params


def test_prepare_pipeline_data_handles_rag_connection_error(
    mock_pipeline_context, mock_adapter, mock_run_params, caplog
):
    """Test that connection errors during RAG indexing are caught and logged."""

    # Mock index_documents to raise ConnectionError
    # Note: Patch where it is imported/used
    with patch("egregora.orchestration.pipelines.etl.preparation.index_documents") as mock_index:
        mock_index.side_effect = ConnectionError("Connection refused")

        with patch(
            "egregora.orchestration.pipelines.etl.preparation.create_and_initialize_adapter"
        ) as mock_create_adapter:
            # Setup factory to return our mock context's output format (sink)
            mock_sink = MagicMock()
            mock_sink.documents.return_value = ["doc1"]
            mock_create_adapter.return_value = mock_sink

            # Setup context
            mock_pipeline_context.with_output_sink.return_value = mock_pipeline_context
            mock_pipeline_context.with_adapter.return_value = mock_pipeline_context

            # Mock other dependencies to avoid side effects
            with (
                patch("egregora.orchestration.pipelines.etl.preparation._parse_and_validate_source"),
                patch("egregora.orchestration.pipelines.etl.preparation._setup_content_directories"),
                patch("egregora.orchestration.pipelines.etl.preparation._process_commands_and_avatars"),
                patch("egregora.orchestration.pipelines.etl.preparation._apply_filters"),
                patch("egregora.orchestration.pipelines.etl.preparation.create_windows"),
            ):
                # Execute function
                with caplog.at_level(logging.WARNING):
                    prepare_pipeline_data(mock_adapter, mock_run_params, mock_pipeline_context)

                # Verify warning logged
                assert "RAG backend unavailable" in caplog.text
                assert "Connection refused" in caplog.text


def test_prepare_pipeline_data_handles_rag_value_error(
    mock_pipeline_context, mock_adapter, mock_run_params, caplog
):
    """Test that value errors (invalid data) during RAG indexing are caught and logged."""

    with patch("egregora.orchestration.pipelines.etl.preparation.index_documents") as mock_index:
        mock_index.side_effect = ValueError("Invalid vector dimension")

        with patch(
            "egregora.orchestration.pipelines.etl.preparation.create_and_initialize_adapter"
        ) as mock_create_adapter:
            mock_sink = MagicMock()
            mock_sink.documents.return_value = ["doc1"]
            mock_create_adapter.return_value = mock_sink

            mock_pipeline_context.with_output_sink.return_value = mock_pipeline_context
            mock_pipeline_context.with_adapter.return_value = mock_pipeline_context

            with (
                patch("egregora.orchestration.pipelines.etl.preparation._parse_and_validate_source"),
                patch("egregora.orchestration.pipelines.etl.preparation._setup_content_directories"),
                patch("egregora.orchestration.pipelines.etl.preparation._process_commands_and_avatars"),
                patch("egregora.orchestration.pipelines.etl.preparation._apply_filters"),
                patch("egregora.orchestration.pipelines.etl.preparation.create_windows"),
            ):
                with caplog.at_level(logging.WARNING):
                    prepare_pipeline_data(mock_adapter, mock_run_params, mock_pipeline_context)

                assert "Invalid document data for RAG indexing" in caplog.text
                assert "Invalid vector dimension" in caplog.text


def test_prepare_pipeline_data_handles_rag_os_error(
    mock_pipeline_context, mock_adapter, mock_run_params, caplog
):
    """Test that OS errors (permission/disk) during RAG indexing are caught and logged."""

    with patch("egregora.orchestration.pipelines.etl.preparation.index_documents") as mock_index:
        mock_index.side_effect = OSError("Read-only file system")

        with patch(
            "egregora.orchestration.pipelines.etl.preparation.create_and_initialize_adapter"
        ) as mock_create_adapter:
            mock_sink = MagicMock()
            mock_sink.documents.return_value = ["doc1"]
            mock_create_adapter.return_value = mock_sink

            mock_pipeline_context.with_output_sink.return_value = mock_pipeline_context
            mock_pipeline_context.with_adapter.return_value = mock_pipeline_context

            with (
                patch("egregora.orchestration.pipelines.etl.preparation._parse_and_validate_source"),
                patch("egregora.orchestration.pipelines.etl.preparation._setup_content_directories"),
                patch("egregora.orchestration.pipelines.etl.preparation._process_commands_and_avatars"),
                patch("egregora.orchestration.pipelines.etl.preparation._apply_filters"),
                patch("egregora.orchestration.pipelines.etl.preparation.create_windows"),
            ):
                with caplog.at_level(logging.WARNING):
                    prepare_pipeline_data(mock_adapter, mock_run_params, mock_pipeline_context)

                assert "Cannot access RAG storage" in caplog.text
                assert "Read-only file system" in caplog.text
