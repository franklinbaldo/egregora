"""Unit tests for BaseWorker logic."""

from unittest.mock import MagicMock

import pytest

from egregora.orchestration.context import PipelineContext
from egregora.orchestration.worker_base import BaseWorker


@pytest.fixture
def mock_task_store():
    """Create a mock TaskStore."""
    return MagicMock()


@pytest.fixture
def mock_pipeline_context(mock_task_store):
    """Create a mock PipelineContext with a TaskStore."""
    ctx = MagicMock(spec=PipelineContext)
    ctx.task_store = mock_task_store
    return ctx


@pytest.fixture
def mock_pipeline_context_no_store():
    """Create a mock PipelineContext without a TaskStore."""
    ctx = MagicMock(spec=PipelineContext)
    # Simulate missing task_store by setting it to None or not setting it
    ctx.task_store = None
    return ctx


class ConcreteWorker(BaseWorker):
    """Concrete implementation of BaseWorker for testing."""

    def run(self) -> int:
        return 42


def test_init_raises_value_error_missing_task_store(mock_pipeline_context_no_store):
    """Test that __init__ raises ValueError if task_store is missing."""
    with pytest.raises(
        ValueError,
        match=r"TaskStore not found in PipelineContext; it must be initialized and injected.",
    ):
        ConcreteWorker(mock_pipeline_context_no_store)


def test_init_sets_task_store(mock_pipeline_context, mock_task_store):
    """Test that __init__ correctly sets the task_store attribute."""
    worker = ConcreteWorker(mock_pipeline_context)
    assert worker.task_store == mock_task_store
    assert worker.ctx == mock_pipeline_context


def test_run_implementation(mock_pipeline_context):
    """Test that a concrete subclass can implement and execute run."""
    worker = ConcreteWorker(mock_pipeline_context)
    result = worker.run()
    assert result == 42
