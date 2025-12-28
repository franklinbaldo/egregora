"""Unit tests for the BannerWorker."""

import json
from unittest.mock import MagicMock, Mock

import pytest

from egregora.agents.banner.worker import BannerWorker
from egregora.agents.exceptions import BannerTaskDataError, BannerTaskPayloadError


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
