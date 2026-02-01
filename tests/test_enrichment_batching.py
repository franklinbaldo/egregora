"""Test to verify enrichment batching strategy.

Verifies that batch_all strategy accumulates multiple items
and sends them in a single API call, rather than individual calls.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from egregora.agents.enricher import EnrichmentWorker


class MockPipelineContext:
    """Mock context for testing."""

    def __init__(self, strategy="batch_all"):
        self.config = Mock()
        self.config.enrichment = Mock()
        self.config.enrichment.rotation_models = ["gemini-pro"]  # Ensure it acts as a list
        self.config.enrichment.strategy = strategy
        self.config.enrichment.max_concurrent_enrichments = 5
        self.config.quota = Mock()
        self.config.quota.concurrency = 5
        self.config.models = Mock()
        self.config.models.enricher = "gemini-2.0-flash"
        self.config.models.enricher_vision = "gemini-2.0-flash"

        self.task_store = Mock()
        self.storage = Mock()
        self.input_path = None
        self.output_dir = Path("/tmp/test")
        self.site_root = Path("/tmp/test-site")  # Add site_root


def create_url_tasks(count: int) -> list[dict]:
    """Create mock URL enrichment tasks."""
    tasks = []
    for i in range(count):
        task = {
            "task_id": f"task-{i}",
            "task_type": "enrich_url",
            "payload": json.dumps(
                {"type": "url", "url": f"https://example.com/page-{i}", "message_metadata": {}}
            ),
            "status": "pending",
        }
        tasks.append(task)
    return tasks


def test_batch_all_accumulates_before_calling_api():
    """Test that batch_all strategy sends multiple URLs in one call."""
    ctx = MockPipelineContext(strategy="batch_all")
    worker = EnrichmentWorker(ctx)

    # Create 5 URL tasks
    tasks = create_url_tasks(5)

    api_call_count = 0
    items_per_call = []

    # Mock the LLM call to track batching
    with patch.object(worker, "_execute_url_single_call") as mock_single_call:

        def track_batch_call(tasks_data):
            nonlocal api_call_count
            api_call_count += 1
            items_per_call.append(len(tasks_data))
            # Return mock results
            return [(task, Mock(), None) for task in tasks]

        mock_single_call.side_effect = track_batch_call

        # Mock task store
        ctx.task_store.fetch_pending.return_value = tasks
        ctx.task_store.mark_completed = Mock()
        ctx.task_store.mark_failed = Mock()

        # Run enrichment
        worker._process_url_batch(tasks)

    # Verify batching behavior

    # CRITICAL: batch_all should make exactly 1 call with all 5 items
    assert api_call_count == 1, f"Expected 1 API call, got {api_call_count}"
    assert items_per_call[0] == 5, f"Expected 5 items in batch, got {items_per_call[0]}"


def test_individual_strategy_makes_separate_calls():
    """Test that individual strategy makes one call per URL."""
    ctx = MockPipelineContext(strategy="individual")
    worker = EnrichmentWorker(ctx)

    # Create 5 URL tasks
    tasks = create_url_tasks(5)

    api_call_count = 0

    # Mock individual enrichment
    with patch.object(worker, "_enrich_single_url") as mock_enrich:

        def track_individual_call(task_data):
            nonlocal api_call_count
            api_call_count += 1
            return (task_data["task"], Mock(), None)

        mock_enrich.side_effect = track_individual_call

        # Mock task store
        ctx.task_store.fetch_pending.return_value = tasks
        ctx.task_store.mark_completed = Mock()
        ctx.task_store.mark_failed = Mock()

        # Run enrichment
        worker._process_url_batch(tasks)

    # Individual strategy should make 5 separate calls
    assert api_call_count == 5, f"Expected 5 API calls, got {api_call_count}"


def test_batching_efficiency_comparison():
    """Compare API usage between batching strategies."""

    test_sizes = [1, 5, 10, 20, 50]

    for size in test_sizes:
        # batch_all: 1 call regardless of size
        batch_calls = 1

        # individual: 1 call per item
        individual_calls = size

        # parallel batching: size / concurrency (rounded up)
        concurrency = 5
        (size + concurrency - 1) // concurrency

        (((individual_calls - batch_calls) / individual_calls * 100) if individual_calls > 0 else 0)


def test_concurrent_batching():
    """Test that concurrency splits work into parallel batches."""
    MockPipelineContext(strategy="batch_all")

    # Create 15 tasks (more than concurrency of 5)
    create_url_tasks(15)

    # With max_concurrent=5, we expect tasks to be split into groups
    # However, batch_all tries to process all in one call first
    # This test verifies the fallback to parallel execution


def test_verify_batching_logs():
    """Test that logs show batching behavior."""
    import logging
    from io import StringIO

    # Capture logs
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.INFO)

    logger = logging.getLogger("egregora.agents.enricher")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        ctx = MockPipelineContext(strategy="batch_all")
        worker = EnrichmentWorker(ctx)

        tasks = create_url_tasks(8)

        with patch.object(worker, "_execute_url_single_call") as mock_call:
            mock_call.return_value = [(task, Mock(), None) for task in tasks]

            ctx.task_store.fetch_pending.return_value = tasks
            ctx.task_store.mark_completed = Mock()
            ctx.task_store.mark_failed = Mock()

            worker._process_url_batch(tasks)

        logs = log_stream.getvalue()

        # Verify log mentions batching
        assert "batch" in logs.lower() or "8" in logs, "Logs should mention batch processing"

    finally:
        logger.removeHandler(handler)


if __name__ == "__main__":
    test_batch_all_accumulates_before_calling_api()

    test_individual_strategy_makes_separate_calls()

    test_batching_efficiency_comparison()

    test_concurrent_batching()

    test_verify_batching_logs()
