"""Step definitions for enrichment feature."""

import json
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pytest_bdd import given, scenarios, then, when, parsers

from egregora.agents.enricher import EnrichmentWorker
from egregora.agents.exceptions import MediaStagingError

scenarios("../features/enrichment.feature")


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------


class MockPipelineContext:
    """Mock context for testing."""

    def __init__(self, strategy="batch_all", input_path=None):
        self.config = Mock()
        self.config.enrichment = Mock()
        self.config.enrichment.rotation_models = ["gemini-pro"]
        self.config.enrichment.strategy = strategy
        self.config.enrichment.max_concurrent_enrichments = 5
        self.config.quota = Mock()
        self.config.quota.concurrency = 5
        self.config.models = Mock()
        self.config.models.enricher = "gemini-2.0-flash"
        self.config.models.enricher_vision = "gemini-2.0-flash"

        self.task_store = Mock()
        self.storage = Mock()
        self.input_path = input_path
        self.output_dir = Path("/tmp/test")
        self.site_root = Path("/tmp/test-site")


@pytest.fixture
def context():
    """Shared context for steps."""
    return {"worker": None, "pipeline_ctx": None, "tasks": [], "api_call_count": 0, "items_per_call": []}


@pytest.fixture(autouse=True)
def mock_api_keys():
    """Mock API keys to prevent initialization errors."""
    with patch("egregora.llm.api_keys.get_google_api_keys", return_value=["dummy-key"]):
        with patch("egregora.llm.api_keys.get_google_api_key", return_value="dummy-key"):
            yield


@pytest.fixture
def cleanup_temp_zip():
    """Cleanup any temporary zip files created."""
    created_files = []
    yield created_files
    for f in created_files:
        if f.exists():
            f.unlink()


# ---------------------------------------------------------------------------
# Given Steps
# ---------------------------------------------------------------------------


@given('the enrichment strategy is "batch_all"')
def strategy_batch_all(context):
    context["pipeline_ctx"] = MockPipelineContext(strategy="batch_all")
    context["worker"] = EnrichmentWorker(context["pipeline_ctx"])


@given('the enrichment strategy is "individual"')
def strategy_individual(context):
    context["pipeline_ctx"] = MockPipelineContext(strategy="individual")
    context["worker"] = EnrichmentWorker(context["pipeline_ctx"])


@given('there are 5 pending URL enrichment tasks')
def create_5_tasks(context):
    tasks = []
    for i in range(5):
        task = {
            "task_id": f"task-{i}",
            "task_type": "enrich_url",
            "payload": json.dumps(
                {"type": "url", "url": f"https://example.com/page-{i}", "message_metadata": {}}
            ),
            "status": "pending",
        }
        tasks.append(task)
    context["tasks"] = tasks

    # Mock task store
    context["pipeline_ctx"].task_store.fetch_pending.return_value = tasks
    context["pipeline_ctx"].task_store.mark_completed = Mock()
    context["pipeline_ctx"].task_store.mark_failed = Mock()


@given("an enrichment task with no filename in payload")
def task_no_filename(context):
    context["pipeline_ctx"] = MockPipelineContext()
    context["worker"] = EnrichmentWorker(context["pipeline_ctx"])
    context["current_task"] = {"task_id": "test_task"}
    context["current_payload"] = {"original_filename": None, "filename": None}


@given("the input zip file does not exist")
def zip_not_exist(context):
    context["pipeline_ctx"] = MockPipelineContext(input_path=Path("/non/existent/file.zip"))
    context["worker"] = EnrichmentWorker(context["pipeline_ctx"])


@given('an enrichment task for file "test.jpg"')
def task_test_jpg(context):
    context["current_task"] = {"task_id": "test_task"}
    context["current_payload"] = {"original_filename": "test.jpg", "filename": "test.jpg"}


@given("a valid input zip file")
def valid_zip_file(context, cleanup_temp_zip, tmp_path):
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("info.txt", "this is a test zip file")

    cleanup_temp_zip.append(zip_path)

    context["pipeline_ctx"] = MockPipelineContext(input_path=zip_path)
    context["worker"] = EnrichmentWorker(context["pipeline_ctx"])


@given('an enrichment task for file "missing.jpg" which is not in the zip')
def task_missing_jpg(context):
    context["current_task"] = {"task_id": "test_task"}
    context["current_payload"] = {"original_filename": "missing.jpg", "filename": "missing.jpg"}


# ---------------------------------------------------------------------------
# When Steps
# ---------------------------------------------------------------------------


@when("the enrichment worker processes the batch")
def process_batch(context):
    worker = context["worker"]
    tasks = context["tasks"]
    strategy = context["pipeline_ctx"].config.enrichment.strategy

    # Mock the API calling methods based on strategy
    if strategy == "batch_all":
        with patch.object(worker, "_execute_url_single_call") as mock_single:
            def side_effect(tasks_data):
                context["api_call_count"] += 1
                context["items_per_call"].append(len(tasks_data))
                return [(task, Mock(), None) for task in tasks]

            mock_single.side_effect = side_effect
            worker._process_url_batch(tasks)

    else:  # individual
        with patch.object(worker, "_enrich_single_url") as mock_enrich:
            def side_effect(task_data):
                context["api_call_count"] += 1
                return (task_data["task"], Mock(), None)

            mock_enrich.side_effect = side_effect
            worker._process_url_batch(tasks)


@when("the worker attempts to stage the file")
def stage_file(context):
    worker = context["worker"]
    task = context["current_task"]
    payload = context["current_payload"]

    try:
        worker._stage_file(task, payload)
        context["exception"] = None
    except Exception as e:
        context["exception"] = e


# ---------------------------------------------------------------------------
# Then Steps
# ---------------------------------------------------------------------------


@then("the worker should make exactly 1 API call")
def assert_one_call(context):
    assert context["api_call_count"] == 1, f"Expected 1 call, got {context['api_call_count']}"


@then("the batch API call should contain 5 items")
def assert_batch_items(context):
    assert context["items_per_call"][0] == 5, f"Expected 5 items, got {context['items_per_call'][0]}"


@then("the worker should make 5 API calls")
def assert_five_calls(context):
    assert context["api_call_count"] == 5, f"Expected 5 calls, got {context['api_call_count']}"


@then(parsers.parse('a MediaStagingError should be raised matching "{message}"'))
def assert_error_message(context, message):
    assert isinstance(context["exception"], MediaStagingError)
    assert message in str(context["exception"]), f"Expected '{message}' in '{context['exception']}'"
