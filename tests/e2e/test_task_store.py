import uuid
import pytest
import json
from datetime import datetime
from egregora.database.task_store import TaskStore
from egregora.database.duckdb_manager import DuckDBStorageManager

@pytest.fixture
def task_store(tmp_path):
    db_path = tmp_path / "test_tasks.duckdb"
    storage = DuckDBStorageManager(db_path)
    store = TaskStore(storage)
    yield store
    storage.close()

def test_enqueue_and_fetch(task_store):
    run_id = uuid.uuid4()
    payload = {"foo": "bar"}
    task_id = task_store.enqueue("test_task", payload, run_id)

    assert task_id is not None

    pending = task_store.fetch_pending()
    assert len(pending) == 1
    task = pending[0]
    assert task["task_type"] == "test_task"

    # Handle both string and dict payload returns (depending on Ibis version/adapter)
    returned_payload = task["payload"]
    if isinstance(returned_payload, str):
        returned_payload = json.loads(returned_payload)

    assert returned_payload == payload
    assert str(task["task_id"]) == str(task_id)
    assert task["status"] == "pending"

def test_fetch_filtering(task_store):
    run_id = uuid.uuid4()
    task_store.enqueue("type_a", {"val": 1}, run_id)
    task_store.enqueue("type_b", {"val": 2}, run_id)

    tasks_a = task_store.fetch_pending(task_type="type_a")
    assert len(tasks_a) == 1
    assert tasks_a[0]["task_type"] == "type_a"

    tasks_b = task_store.fetch_pending(task_type="type_b")
    assert len(tasks_b) == 1
    assert tasks_b[0]["task_type"] == "type_b"

    tasks_all = task_store.fetch_pending()
    assert len(tasks_all) == 2

def test_mark_completed(task_store):
    run_id = uuid.uuid4()
    task_id = task_store.enqueue("test_task", {}, run_id)

    task_store.mark_completed(task_id)

    pending = task_store.fetch_pending()
    assert len(pending) == 0

    # Verify status in DB
    t = task_store.storage.read_table("tasks")
    rows = t.filter(t.task_id == uuid.UUID(task_id)).execute().to_dict(orient="records")
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
    assert rows[0]["processed_at"] is not None

def test_mark_failed(task_store):
    run_id = uuid.uuid4()
    task_id = task_store.enqueue("test_task", {}, run_id)

    error_msg = "Something went wrong"
    task_store.mark_failed(task_id, error_msg)

    pending = task_store.fetch_pending()
    assert len(pending) == 0

    t = task_store.storage.read_table("tasks")
    rows = t.filter(t.task_id == uuid.UUID(task_id)).execute().to_dict(orient="records")
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["error"] == error_msg

def test_mark_superseded(task_store):
    run_id = uuid.uuid4()
    task_id = task_store.enqueue("test_task", {}, run_id)

    task_store.mark_superseded(task_id, "Old task")

    pending = task_store.fetch_pending()
    assert len(pending) == 0

    t = task_store.storage.read_table("tasks")
    rows = t.filter(t.task_id == uuid.UUID(task_id)).execute().to_dict(orient="records")
    assert len(rows) == 1
    assert rows[0]["status"] == "superseded"
    assert rows[0]["error"] == "Old task"
