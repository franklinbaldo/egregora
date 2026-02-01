"""Unit tests for the BannerWorker."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from egregora.agents.banner.worker import BannerWorker
from egregora.agents.banner.exceptions import BannerTaskDataError, BannerTaskPayloadError


@pytest.fixture
def mock_context():
    """Fixture for a mocked PipelineContext."""
    ctx = Mock()
    ctx.task_store = MagicMock()
    return ctx


def test_parse_task_missing_payload(mock_context):
    """Should raise BannerTaskPayloadError if payload is missing."""
    worker = BannerWorker(mock_context)
    task = {"task_id": "123"}

    with pytest.raises(BannerTaskPayloadError, match="Missing payload"):
        worker._parse_task(task)

    mock_context.task_store.mark_failed.assert_called_once_with("123", "Missing payload")


def test_parse_task_invalid_json_payload(mock_context):
    """Should raise BannerTaskPayloadError if payload is invalid JSON."""
    worker = BannerWorker(mock_context)
    task = {"task_id": "456", "payload": "{not json}"}

    with pytest.raises(BannerTaskPayloadError, match="Invalid payload JSON"):
        worker._parse_task(task)

    mock_context.task_store.mark_failed.assert_called_once_with("456", "Invalid payload JSON")


def test_parse_task_missing_required_data(mock_context):
    """Should raise BannerTaskDataError if slug or title is missing."""
    worker = BannerWorker(mock_context)
    payload = {"summary": "A summary"}
    task = {"task_id": "789", "payload": json.dumps(payload)}

    with pytest.raises(BannerTaskDataError) as excinfo:
        worker._parse_task(task)

    assert "post_slug" in str(excinfo.value)
    assert "title" in str(excinfo.value)
    mock_context.task_store.mark_failed.assert_called_once_with("789", "Missing slug/title")


def test_parse_task_missing_title(mock_context):
    """Should raise BannerTaskDataError if title is missing."""
    worker = BannerWorker(mock_context)
    payload = {"post_slug": "a-slug"}
    task = {"task_id": "789", "payload": json.dumps(payload)}

    with pytest.raises(BannerTaskDataError) as excinfo:
        worker._parse_task(task)

    assert "title" in str(excinfo.value)
    mock_context.task_store.mark_failed.assert_called_once_with("789", "Missing slug/title")


def test_parse_task_success(mock_context):
    """Should successfully parse a valid task."""
    worker = BannerWorker(mock_context)
    payload = {
        "post_slug": "a-slug",
        "title": "A Title",
        "summary": "A summary",
        "language": "en-US",
        "run_id": "run-abc",
    }
    task = {"task_id": "101", "payload": json.dumps(payload)}

    entry = worker._parse_task(task)

    assert entry is not None
    assert entry.task_id == "101"
    assert entry.slug == "a-slug"
    assert entry.title == "A Title"
    assert entry.summary == "A summary"
    assert entry.language == "en-US"
    assert entry.metadata == {"run_id": "run-abc"}
    mock_context.task_store.mark_failed.assert_not_called()


def test_run_no_tasks(mock_context):
    """Should return 0 if there are no pending tasks."""
    mock_context.task_store.fetch_pending.return_value = []
    worker = BannerWorker(mock_context)

    result = worker.run()

    assert result == 0
    mock_context.task_store.fetch_pending.assert_called_once_with(task_type="generate_banner")


@patch("egregora.agents.banner.worker.persist_banner_document")
@patch("egregora.agents.banner.worker.BannerBatchProcessor")
def test_run_with_mixed_tasks(mock_processor, mock_persist, mock_context):
    """Should handle a mix of valid and invalid tasks."""
    valid_task_payload = {"post_slug": "a-slug", "title": "A Title"}
    tasks = [
        {"task_id": "1", "payload": json.dumps(valid_task_payload)},
        {"task_id": "2"},
        {"task_id": "3", "payload": json.dumps({"post_slug": "another-slug"})},
    ]
    mock_context.task_store.fetch_pending.return_value = tasks

    mock_generator = mock_processor.return_value
    mock_result = Mock()
    mock_result.success = True
    mock_result.document = Mock()
    mock_result.task = Mock()
    mock_result.task.task_id = "1"
    mock_generator.process_tasks.return_value = [mock_result]
    mock_persist.return_value = "/path/to/banner.png"

    worker = BannerWorker(mock_context)
    result = worker.run()

    assert result == 3

    assert mock_generator.process_tasks.call_count == 1
    processed_tasks_args = mock_generator.process_tasks.call_args[0][0]
    assert len(processed_tasks_args) == 1
    assert processed_tasks_args[0].task_id == "1"

    calls = mock_context.task_store.mark_failed.call_args_list
    assert len(calls) == 2
    assert calls[0].args == ("2", "Missing payload")
    assert calls[1].args == ("3", "Missing slug/title")

    mock_persist.assert_called_once()
    mock_context.task_store.mark_completed.assert_called_once_with("1")


@patch("egregora.agents.banner.worker.persist_banner_document")
@patch("egregora.agents.banner.worker.BannerBatchProcessor")
def test_run_success(mock_processor, mock_persist, mock_context):
    """Should handle a successful banner generation."""
    valid_task_payload = {"post_slug": "a-slug", "title": "A Title"}
    tasks = [{"task_id": "1", "payload": json.dumps(valid_task_payload)}]
    mock_context.task_store.fetch_pending.return_value = tasks

    mock_generator = mock_processor.return_value
    mock_result = Mock()
    mock_result.success = True
    mock_result.document = Mock()
    mock_result.task = Mock()
    mock_result.task.task_id = "1"
    mock_generator.process_tasks.return_value = [mock_result]
    mock_persist.return_value = "/path/to/banner.png"

    worker = BannerWorker(mock_context)
    result = worker.run()

    assert result == 1

    mock_generator.process_tasks.assert_called_once()
    mock_persist.assert_called_once()
    mock_context.task_store.mark_completed.assert_called_once_with("1")
    mock_context.task_store.mark_failed.assert_not_called()


@patch("egregora.agents.banner.worker.persist_banner_document")
@patch("egregora.agents.banner.worker.BannerBatchProcessor")
def test_run_with_failed_generation(mock_processor, mock_persist, mock_context):
    """Should handle a failed banner generation."""
    valid_task_payload = {"post_slug": "a-slug", "title": "A Title"}
    tasks = [{"task_id": "1", "payload": json.dumps(valid_task_payload)}]
    mock_context.task_store.fetch_pending.return_value = tasks

    mock_generator = mock_processor.return_value
    mock_result = Mock()
    mock_result.success = False
    mock_result.error = "Something went wrong"
    mock_result.task = Mock()
    mock_result.task.task_id = "1"
    mock_generator.process_tasks.return_value = [mock_result]

    worker = BannerWorker(mock_context)
    result = worker.run()

    assert result == 1

    mock_generator.process_tasks.assert_called_once()
    mock_persist.assert_not_called()
    mock_context.task_store.mark_completed.assert_not_called()
    mock_context.task_store.mark_failed.assert_called_once_with("1", "Something went wrong")


@patch("egregora.agents.banner.worker.BannerBatchProcessor")
def test_run_with_all_invalid_tasks(mock_processor, mock_context):
    """Should handle a mix of valid and invalid tasks."""
    tasks = [
        {"task_id": "2"},
        {"task_id": "3", "payload": json.dumps({"post_slug": "another-slug"})},
    ]
    mock_context.task_store.fetch_pending.return_value = tasks
    mock_generator = mock_processor.return_value

    worker = BannerWorker(mock_context)
    result = worker.run()

    assert result == 2

    mock_generator.process_tasks.assert_not_called()
    calls = mock_context.task_store.mark_failed.call_args_list
    assert len(calls) == 2
    assert calls[0].args == ("2", "Missing payload")
    assert calls[1].args == ("3", "Missing slug/title")
    mock_context.task_store.mark_completed.assert_not_called()
