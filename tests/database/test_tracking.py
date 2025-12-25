
import pytest
import uuid
from unittest.mock import MagicMock, call
from datetime import datetime
import ibis

from src.egregora.database.run_store import RunStore
from src.egregora.database.tracking import run_stage_with_tracking, RunContext

def stage_func_success(input_table):
    return input_table

def stage_func_failure(input_table):
    raise ValueError("Test error")

def test_run_stage_with_tracking_success():
    # Arrange
    mock_run_store = MagicMock(spec=RunStore)
    mock_storage = MagicMock()
    mock_run_store.storage = mock_storage

    context = RunContext.create(stage="test_stage")
    mock_input_table = MagicMock(spec=ibis.Table)
    mock_input_table.count.return_value.execute.return_value = 10

    # Act
    run_stage_with_tracking(
        stage_func=stage_func_success,
        context=context,
        run_store=mock_run_store,
        input_table=mock_input_table,
    )

    # Assert
    assert mock_run_store.mark_run_started.call_count == 1
    assert mock_run_store.mark_run_completed.call_count == 1
    assert mock_run_store.mark_run_failed.call_count == 0

def test_run_stage_with_tracking_failure():
    # Arrange
    mock_run_store = MagicMock(spec=RunStore)
    mock_storage = MagicMock()
    mock_run_store.storage = mock_storage

    context = RunContext.create(stage="test_stage")
    mock_input_table = MagicMock(spec=ibis.Table)
    mock_input_table.count.return_value.execute.return_value = 10

    # Act & Assert
    with pytest.raises(ValueError, match="Test error"):
        run_stage_with_tracking(
            stage_func=stage_func_failure,
            context=context,
            run_store=mock_run_store,
            input_table=mock_input_table,
        )

    # Assert
    assert mock_run_store.mark_run_started.call_count == 1
    assert mock_run_store.mark_run_completed.call_count == 0
    assert mock_run_store.mark_run_failed.call_count == 1
