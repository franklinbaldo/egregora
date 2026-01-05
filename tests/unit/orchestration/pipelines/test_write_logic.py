from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import ibis
import ibis.common.exceptions
import pytest

from egregora.orchestration.pipelines.write import (
    Conversation,
    PreparedPipelineData,
    _parse_and_validate_source,
    get_pending_conversations,
    process_item,
)


# Mocks and Fixtures
@pytest.fixture
def mock_ibis_table():
    """Returns a MagicMock for an Ibis table."""
    table = MagicMock(spec=ibis.expr.types.Table)
    table.count.return_value.execute.return_value = 1
    table.execute.return_value.to_dict.return_value = [{"message": "test"}]
    table.to_pyarrow.return_value.to_pylist.return_value = [{"message": "test"}]
    return table


@pytest.fixture
def mock_prepared_pipeline_data(mock_ibis_table):
    """Returns a mock PreparedPipelineData object."""
    context = MagicMock()
    context.config.pipeline.max_windows = 10
    dataset = MagicMock(spec=PreparedPipelineData)
    dataset.context = context
    dataset.windows_iterator = [MagicMock(table=mock_ibis_table, size=10)]
    dataset.enable_enrichment = False
    return dataset


@pytest.fixture
def mock_conversation(mock_ibis_table):
    """Returns a mock Conversation object."""
    conversation = MagicMock(spec=Conversation)
    conversation.context = MagicMock()
    conversation.messages_table = mock_ibis_table
    conversation.window = MagicMock()
    conversation.window.start_time = datetime.now()
    conversation.window.end_time = datetime.now()
    conversation.adapter_info = ("", "")
    return conversation


def test_get_pending_conversations_handles_ibis_error_on_count(mock_prepared_pipeline_data, caplog):
    """
    Verify get_pending_conversations gracefully handles IbisError when counting enriched table.
    """
    failing_table = MagicMock(spec=ibis.expr.types.Table)
    failing_table.count.return_value.execute.side_effect = ibis.common.exceptions.IbisError("DB error")

    mock_prepared_pipeline_data.enable_enrichment = True

    # We need to patch perform_enrichment as it's called inside the generator
    with patch("egregora.orchestration.pipelines.write.perform_enrichment", return_value=failing_table):
        with caplog.at_level(logging.DEBUG):
            # Consume the generator
            conversations = list(get_pending_conversations(mock_prepared_pipeline_data))

    # The generator should still yield the conversation, just with a logging side-effect
    assert len(conversations) == 1
    assert "Failed to count enriched table" in caplog.text
    assert "DB error" in caplog.text


def test_process_item_handles_ibis_error_on_count(mock_conversation, caplog):
    """
    Verify process_item gracefully handles IbisError when counting messages table.
    """
    mock_conversation.messages_table.count.return_value.execute.side_effect = (
        ibis.common.exceptions.IbisError("Count failed")
    )

    with caplog.at_level(logging.WARNING):
        # Patch the downstream calls to prevent them from executing as we are only testing the error handling
        with (
            patch("egregora.orchestration.pipelines.write.extract_commands_list", return_value=[]),
            patch("egregora.orchestration.pipelines.write.filter_commands", return_value=[]),
            patch("egregora.orchestration.pipelines.write.PipelineFactory.create_writer_resources"),
            patch("egregora.orchestration.pipelines.write.write_posts_for_window", return_value={}),
            patch("egregora.orchestration.pipelines.write.generate_profile_posts", return_value=[]),
            patch("egregora.orchestration.pipelines.write.process_background_tasks"),
        ):
            process_item(mock_conversation)

    assert "Failed to count messages_table" in caplog.text
    assert "Count failed" in caplog.text
    # Verify that the function continued to the next step, which is converting the table to a list
    mock_conversation.messages_table.execute.assert_called_once()


def test_process_item_handles_ibis_error_on_execute(mock_conversation, caplog):
    """
    Verify process_item gracefully handles IbisError on execute and falls back to pyarrow.
    """
    mock_conversation.messages_table.execute.side_effect = ibis.common.exceptions.IbisError("Execute failed")

    with caplog.at_level(logging.WARNING):
        with (
            patch("egregora.orchestration.pipelines.write.extract_commands_list", return_value=[]),
            patch("egregora.orchestration.pipelines.write.filter_commands", return_value=[]),
            patch("egregora.orchestration.pipelines.write.PipelineFactory.create_writer_resources"),
            patch("egregora.orchestration.pipelines.write.write_posts_for_window", return_value={}),
            patch("egregora.orchestration.pipelines.write.generate_profile_posts", return_value=[]),
            patch("egregora.orchestration.pipelines.write.process_background_tasks"),
        ):
            process_item(mock_conversation)

    assert "execute().to_dict() failed" in caplog.text
    assert "Execute failed" in caplog.text
    # Verify that the fallback to pyarrow was attempted
    mock_conversation.messages_table.to_pyarrow.assert_called_once()


def test_process_item_handles_ibis_error_on_fallback(mock_conversation, caplog):
    """
    Verify process_item gracefully handles ibis error on fallback.
    """
    mock_conversation.messages_table.execute.side_effect = ibis.common.exceptions.IbisError("Execute failed")
    mock_conversation.messages_table.to_pyarrow.return_value.to_pylist.side_effect = (
        ibis.common.exceptions.IbisError("Ibis fallback failed")
    )

    with caplog.at_level(logging.WARNING):
        with (
            patch("egregora.orchestration.pipelines.write.extract_commands_list") as mock_extract,
            patch("egregora.orchestration.pipelines.write.filter_commands", return_value=[]),
            patch("egregora.orchestration.pipelines.write.PipelineFactory.create_writer_resources"),
            patch("egregora.orchestration.pipelines.write.write_posts_for_window", return_value={}),
            patch("egregora.orchestration.pipelines.write.generate_profile_posts", return_value=[]),
            patch("egregora.orchestration.pipelines.write.process_background_tasks"),
        ):
            process_item(mock_conversation)

    assert "to_pyarrow().to_pylist() also failed" in caplog.text
    assert "Ibis fallback failed" in caplog.text
    # After all failures, the messages_list should be empty
    mock_extract.assert_called_once_with([])


def test_parse_and_validate_source_handles_duckdb_error(caplog):
    """
    Verify _parse_and_validate_source handles duckdb.Error on insert.
    """
    mock_adapter = MagicMock()
    mock_adapter.parse.return_value = MagicMock(spec=ibis.expr.types.Table)
    mock_adapter.parse.return_value.count.return_value.execute.return_value = 1
    mock_adapter.get_metadata.return_value = {"group_name": "Test Group"}

    mock_ctx = MagicMock()
    mock_ctx.storage.ibis_conn.insert.side_effect = duckdb.Error("Insert failed")

    with caplog.at_level(logging.WARNING):
        table = _parse_and_validate_source(
            adapter=mock_adapter, input_path=Path("dummy.zip"), timezone="UTC", ctx=mock_ctx
        )

    assert "Failed to materialize messages to DuckDB" in caplog.text
    assert "Insert failed" in caplog.text
    # The original, in-memory table should be returned
    assert table == mock_adapter.parse.return_value
