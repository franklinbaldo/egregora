"""Integration test for async pipeline tasks.

Verifies that the task store integration with the pipeline machinery works as expected.
"""

import uuid
import json
from datetime import datetime, UTC
from unittest.mock import MagicMock, patch
import pytest

from egregora.orchestration.context import PipelineContext, PipelineConfig, PipelineState
from egregora.orchestration.workers import BannerWorker, ProfileWorker
from egregora.agents.capabilities import AsyncBannerCapability, AsyncProfileCapability
from egregora.agents.types import WriterResources
from egregora.database.task_store import TaskStore
from egregora.data_primitives.document import Document, DocumentType

@pytest.fixture
def mock_pipeline_context():
    """Create a mock pipeline context with a real-ish TaskStore (mocked storage)."""
    # Mock storage for task store
    mock_storage = MagicMock()
    mock_storage.list_tables.return_value = ["tasks"]

    # Mock read_table to simulate tasks
    mock_table = MagicMock()
    mock_storage.read_table.return_value = mock_table

    # Mock ibis conn insert
    mock_storage.ibis_conn.insert = MagicMock()

    # Mock TaskStore
    task_store = MagicMock(spec=TaskStore)

    # Mock output sink
    output_sink = MagicMock()
    output_sink.url_convention.canonical_url.return_value = "http://test/banner.jpg"

    # Create minimal context
    state = MagicMock(spec=PipelineState)
    state.task_store = task_store
    state.output_format = output_sink

    config = MagicMock(spec=PipelineConfig)

    ctx = MagicMock(spec=PipelineContext)
    ctx.task_store = task_store
    ctx.output_format = output_sink

    return ctx

def test_banner_worker_processes_tasks(mock_pipeline_context):
    """Test that BannerWorker processes pending tasks."""
    ctx = mock_pipeline_context
    task_store = ctx.task_store

    # Setup pending tasks
    task_id = str(uuid.uuid4())
    payload = {
        "post_slug": "test-post",
        "title": "Test Title",
        "summary": "Test Summary"
    }
    task = {
        "task_id": task_id,
        "task_type": "generate_banner",
        "payload": payload,
        "status": "pending",
        "run_id": str(uuid.uuid4())
    }
    task_store.fetch_pending.return_value = [task]

    # Patch generate_banner to succeed
    with patch("egregora.orchestration.workers.generate_banner") as mock_gen:
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.document = Document(
            content=b"image data",
            type=DocumentType.MEDIA,
            metadata={"filename": "banner.jpg"}
        )
        mock_gen.return_value = mock_result

        worker = BannerWorker(ctx)
        count = worker.run()

        assert count == 1

        # Verify persistence
        ctx.output_format.persist.assert_called_once()

        # Verify task completion
        task_store.mark_completed.assert_called_with(task_id)

def test_profile_worker_coalescing(mock_pipeline_context):
    """Test that ProfileWorker coalesces multiple updates for same author."""
    ctx = mock_pipeline_context
    task_store = ctx.task_store

    author_uuid = "author-123"

    # Create 3 tasks for same author
    tasks = []
    for i in range(3):
        tasks.append({
            "task_id": f"task-{i}",
            "task_type": "update_profile",
            "payload": {
                "author_uuid": author_uuid,
                "content": f"Update {i}"
            },
            "status": "pending",
            "created_at": datetime.now(UTC) # Logic doesn't strictly depend on this if ordered by list index
        })

    task_store.fetch_pending.return_value = tasks

    worker = ProfileWorker(ctx)
    count = worker.run()

    # Should process 1 (the last one)
    assert count == 1

    # Verify superseded calls
    # Task 0 and 1 should be superseded
    task_store.mark_superseded.assert_any_call("task-0", reason="Superseded by task task-2")
    task_store.mark_superseded.assert_any_call("task-1", reason="Superseded by task task-2")

    # Verify completion of last task
    task_store.mark_completed.assert_called_with("task-2")

    # Verify persistence of last content
    # Get the args passed to persist
    args, _ = ctx.output_format.persist.call_args
    doc = args[0]
    assert doc.content == "Update 2"
    assert doc.metadata["uuid"] == author_uuid

def test_capability_delegation():
    """Test that capabilities correctly enqueue tasks."""
    resources = MagicMock(spec=WriterResources)
    task_store = MagicMock(spec=TaskStore)
    resources.task_store = task_store

    run_id = uuid.uuid4()

    # Banner Capability
    banner_cap = AsyncBannerCapability(resources, run_id)
    banner_cap.schedule("slug", "Title", "Summary")

    task_store.enqueue.assert_called_with(
        task_type="generate_banner",
        payload={"post_slug": "slug", "title": "Title", "summary": "Summary"},
        run_id=run_id
    )

    # Profile Capability
    profile_cap = AsyncProfileCapability(resources, run_id)
    profile_cap.schedule("author-1", "Content")

    task_store.enqueue.assert_called_with(
        task_type="update_profile",
        payload={"author_uuid": "author-1", "content": "Content"},
        run_id=run_id
    )
