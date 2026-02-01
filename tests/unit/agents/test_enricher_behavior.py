import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.enricher import EnrichmentOutput, EnrichmentWorker, schedule_enrichment
from egregora.config.settings import EnrichmentSettings
from egregora.data_primitives.document import Document, DocumentType
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.exceptions import CacheKeyNotFoundError

# ---------------------------------------------------------------------------
# Scheduling Tests
# ---------------------------------------------------------------------------


def test_schedule_enrichment_enqueue_url_tasks():
    """Verify that URL enrichment tasks are correctly scheduled."""
    # Setup
    mock_messages = MagicMock()
    # Ensure count > 0 so it proceeds
    mock_messages.count().execute.return_value = 10

    # Mock Repository result
    mock_repo = MagicMock()
    candidates = [
        ("http://example.com/1", {"ts": datetime(2023, 1, 1, tzinfo=UTC), "source": "s1"}),
        ("http://example.com/2", {"ts": datetime(2023, 1, 1, tzinfo=UTC), "source": "s1"}),
    ]
    mock_repo.get_url_enrichment_candidates.return_value = candidates

    mock_context = MagicMock()
    mock_context.task_store = MagicMock()
    # Simulate cache miss
    mock_context.cache.load.side_effect = CacheKeyNotFoundError("miss")

    settings = EnrichmentSettings(enable_url=True, max_enrichments=5, enable_media=False)

    with patch("egregora.agents.enricher.url.MessageRepository", return_value=mock_repo):
        schedule_enrichment(mock_messages, {}, settings, mock_context)

    # Verify
    # Should call enqueue_batch once for URLs (since media is disabled)
    mock_context.task_store.enqueue_batch.assert_called()
    # Get args of the first call
    batch = mock_context.task_store.enqueue_batch.call_args[0][0]

    assert len(batch) == 2
    assert batch[0][0] == "enrich_url"
    assert batch[0][1]["url"] == "http://example.com/1"
    assert batch[1][0] == "enrich_url"
    assert batch[1][1]["url"] == "http://example.com/2"


def test_schedule_enrichment_respects_max_enrichments():
    """Verify that scheduling respects the max_enrichments limit."""
    mock_messages = MagicMock()
    mock_messages.count().execute.return_value = 10

    mock_repo = MagicMock()
    # 5 candidates
    candidates = [(f"http://example.com/{i}", {"ts": datetime.now(), "source": "s"}) for i in range(5)]
    mock_repo.get_url_enrichment_candidates.return_value = candidates

    mock_context = MagicMock()
    mock_context.task_store = MagicMock()
    mock_context.cache.load.side_effect = CacheKeyNotFoundError("miss")

    # Limit to 2
    settings = EnrichmentSettings(enable_url=True, max_enrichments=2, enable_media=False)

    with patch("egregora.agents.enricher.url.MessageRepository", return_value=mock_repo):
        # Note: MessageRepository.get_url_enrichment_candidates handles the LIMIT at DB level usually,
        # but the scheduler logic relies on what it returns.
        # However, _enqueue_url_enrichments takes max_enrichments.
        # In current implementation, get_url_enrichment_candidates IS passed max_enrichments.
        # But _enqueue_url_enrichments iterates over the results.

        schedule_enrichment(mock_messages, {}, settings, mock_context)

    # Verify that get_url_enrichment_candidates was called with limit=2
    mock_repo.get_url_enrichment_candidates.assert_called_with(mock_messages, 2)


def test_schedule_enrichment_skips_existing_in_db():
    """Verify that URLs already in the database are skipped."""
    mock_messages = MagicMock()
    mock_messages.count().execute.return_value = 10

    mock_repo = MagicMock()
    candidates = [
        ("http://example.com/new", {"ts": datetime.now(), "source": "s"}),
        ("http://example.com/exists", {"ts": datetime.now(), "source": "s"}),
    ]
    mock_repo.get_url_enrichment_candidates.return_value = candidates

    mock_context = MagicMock()
    mock_context.task_store = MagicMock()
    mock_context.cache.load.side_effect = CacheKeyNotFoundError("miss")

    # Mock the DB check for existing URLs
    # db_existing is the result of execute() on the filtered query
    mock_existing_result = MagicMock()
    mock_existing_result.__getitem__.return_value.tolist.return_value = ["http://example.com/exists"]

    # filter().select().execute() chain
    mock_messages.filter.return_value.select.return_value.execute.return_value = mock_existing_result

    settings = EnrichmentSettings(enable_url=True, max_enrichments=10, enable_media=False)

    with patch("egregora.agents.enricher.url.MessageRepository", return_value=mock_repo):
        schedule_enrichment(mock_messages, {}, settings, mock_context)

    # Verify
    batch = mock_context.task_store.enqueue_batch.call_args[0][0]
    assert len(batch) == 1
    assert batch[0][1]["url"] == "http://example.com/new"


# ---------------------------------------------------------------------------
# Execution Tests (EnrichmentWorker.run)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_worker_context():
    ctx = MagicMock(spec=PipelineContext)
    ctx.config = MagicMock()
    ctx.config.enrichment = EnrichmentSettings(enabled=True)

    # Set quota.concurrency to an int to avoid TypeError in _determine_concurrency
    ctx.config.quota.concurrency = 5

    ctx.task_store = MagicMock()
    ctx.input_path = Path("/tmp/fake.zip")
    return ctx


def test_worker_run_processes_url_batch(mock_worker_context):
    """Verify that run() fetches tasks and processes them."""
    # Setup
    worker = EnrichmentWorker(mock_worker_context)

    # Mock task fetch
    task_payload = json.dumps(
        {"url": "http://example.com", "message_metadata": {"ts": "2023-01-01T00:00:00", "source": "test"}}
    )
    tasks = [{"task_id": "t1", "payload": task_payload}]

    mock_worker_context.task_store.fetch_pending.side_effect = [tasks, []]  # URLs, then Media (empty)

    # Mock execution methods to isolate flow testing
    with (
        patch.object(worker.url_handler, "process_batch", return_value=1) as mock_process_url,
        patch.object(worker.media_handler, "process_batch", return_value=0) as mock_process_media,
    ):
        count = worker.run()

        assert count == 1
        mock_process_url.assert_called_once_with(tasks)
        mock_process_media.assert_not_called()  # No media tasks returned


def test_worker_run_processes_media_batch(mock_worker_context):
    """Verify that run() fetches media tasks and processes them."""
    worker = EnrichmentWorker(mock_worker_context)

    # Mock task fetch
    tasks = [{"task_id": "m1", "payload": "{}"}]

    mock_worker_context.task_store.fetch_pending.side_effect = [[], tasks]  # URLs (empty), then Media

    with (
        patch.object(worker.url_handler, "process_batch", return_value=0) as mock_process_url,
        patch.object(worker.media_handler, "process_batch", return_value=1) as mock_process_media,
    ):
        count = worker.run()

        assert count == 1
        mock_process_url.assert_not_called()
        mock_process_media.assert_called_once_with(tasks)


# ---------------------------------------------------------------------------
# Persistence Tests
# ---------------------------------------------------------------------------


def test_persist_url_results_success(mock_worker_context):
    """Verify successful persistence of URL enrichment results."""
    worker = EnrichmentWorker(mock_worker_context)

    # Prepare input
    task = {
        "task_id": "t1",
        "_parsed_payload": {
            "url": "http://example.com",
            "message_metadata": {
                "ts": datetime(2023, 1, 1, tzinfo=UTC),
                "tenant_id": "tenant1",
                "source": "source1",
                "thread_id": None,
                "author_uuid": None,
                "created_at": datetime(2023, 1, 1, tzinfo=UTC),
                "created_by_run": None,
            },
        },
    }
    output = EnrichmentOutput(
        slug="example-slug", markdown="# Example\n\nSummary", title="Example Title", tags=["tag1"]
    )
    results = [(task, output, None)]

    # Mock sink
    mock_sink = MagicMock()
    mock_worker_context.output_sink = mock_sink
    mock_worker_context.library = None  # ensure using sink

    # Act
    worker.url_handler._persist_results(results)

    # Verify Document Persistence
    mock_sink.persist.assert_called_once()
    doc = mock_sink.persist.call_args[0][0]
    assert isinstance(doc, Document)
    assert doc.type == DocumentType.ENRICHMENT_URL
    assert doc.metadata["slug"] == "example-slug"
    assert doc.metadata["url"] == "http://example.com"

    # Verify DB Write
    mock_worker_context.storage.write_table.assert_called_once()
    table_name = mock_worker_context.storage.write_table.call_args[0][1]
    assert table_name == "messages"

    # Verify Task Completion
    mock_worker_context.task_store.mark_completed.assert_called_once_with("t1")


def test_persist_media_results_success(mock_worker_context):
    """Verify successful persistence of Media enrichment results."""
    worker = EnrichmentWorker(mock_worker_context)

    # Prepare input
    task = {
        "task_id": "m1",
        "_parsed_payload": {
            "filename": "test.jpg",
            "original_filename": "test.jpg",
            "media_type": "image/jpeg",
            "message_metadata": {
                "ts": datetime(2023, 1, 1, tzinfo=UTC),
                "created_at": datetime(2023, 1, 1, tzinfo=UTC),
            },
        },
        "_staged_path": "/tmp/staged/test.jpg",
    }

    # Mock result from batch execution
    # result object has .tag, .error, .response
    mock_res = MagicMock()
    mock_res.tag = "m1"
    mock_res.error = None
    mock_res.response = {
        "text": json.dumps(
            {"slug": "test-image", "markdown": "# Test Image", "title": "Test Image", "tags": ["image"]}
        )
    }

    task_map = {"m1": task}

    # Mock filesystem existence check
    with patch("pathlib.Path.exists", return_value=True):
        # Mock sink
        mock_sink = MagicMock()
        mock_worker_context.output_sink = mock_sink
        mock_worker_context.library = None

        # Act
        worker.media_handler._persist_results([mock_res], task_map)

        # Verify
        assert mock_sink.persist.call_count == 2  # 1 Media doc, 1 Enrichment doc

        # Check Media Doc
        media_doc = mock_sink.persist.call_args_list[0][0][0]
        assert media_doc.type == DocumentType.MEDIA
        assert media_doc.metadata["filename"] == "test-image.jpg"  # slug based
        assert media_doc.metadata["source_path"] == "/tmp/staged/test.jpg"

        # Check Enrichment Doc
        enrich_doc = mock_sink.persist.call_args_list[1][0][0]

        # This assertion verifies the fix for correct DocumentType mapping
        assert enrich_doc.type == DocumentType.ENRICHMENT_IMAGE
        assert enrich_doc.metadata["slug"] == "test-image"

        # Verify DB Update for message references
        mock_worker_context.storage.execute_sql.assert_called()

        # Verify Task Completion
        # Media handler uses batch completion if available
        mock_worker_context.task_store.mark_completed_batch.assert_called_once_with(["m1"])
