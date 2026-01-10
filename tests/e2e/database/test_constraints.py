
import uuid
from datetime import datetime, timezone

import duckdb
import pytest
from ibis.backends.base import BaseBackend

from egregora.database.init import initialize_database
from egregora.database.schemas import (
    INGESTION_MESSAGE_SCHEMA,
    TASKS_SCHEMA,
    UNIFIED_SCHEMA,
)


@pytest.fixture
def db_backend(tmp_path) -> BaseBackend:
    """Provides a temporary, in-memory DuckDB database backend."""
    db_path = tmp_path / "test.db"
    backend = duckdb.connect(str(db_path))
    initialize_database(backend)
    return backend


def test_documents_primary_key_constraint(db_backend):
    """Verify that inserting duplicate IDs into the documents table fails."""
    doc_id = str(uuid.uuid4())
    common_data = {
        "id": doc_id,
        "doc_type": "post",
        "status": "draft",
        "content": "Test content",
        "created_at": datetime.now(timezone.utc),
        "source_checksum": "checksum1",
        "title": "Test Title",
        "slug": "test-title",
        "date": datetime.now(timezone.utc).date(),
        "summary": "A summary",
        "authors": ["author1"],
        "tags": ["tag1"],
        "extensions": None,
        "subject_uuid": None,
        "alias": None,
        "avatar_url": None,
        "interests": None,
        "filename": None,
        "mime_type": None,
        "media_type": None,
        "phash": None,
        "window_start": None,
        "window_end": None,
    }

    # Create a DataFrame with one row
    table = db_backend.table("documents", schema=UNIFIED_SCHEMA)
    table.insert([common_data])

    # Expect a constraint violation when inserting the same ID again
    with pytest.raises(duckdb.ConstraintException, match="PRIMARY KEY constraint violated"):
        table.insert([common_data])


def test_tasks_primary_key_constraint(db_backend):
    """Verify that inserting duplicate task_ids into the tasks table fails."""
    task_id = uuid.uuid4()
    common_data = {
        "task_id": task_id,
        "task_type": "test_task",
        "status": "pending",
        "payload": {"data": "test"},
        "created_at": datetime.now(timezone.utc),
        "processed_at": None,
        "error": None,
    }

    table = db_backend.table("tasks", schema=TASKS_SCHEMA)
    table.insert([common_data])

    with pytest.raises(duckdb.ConstraintException, match="PRIMARY KEY constraint violated"):
        table.insert([common_data])


def test_messages_primary_key_constraint(db_backend):
    """Verify that inserting duplicate event_ids into the messages table fails."""
    event_id = str(uuid.uuid4())
    common_data = {
        "event_id": event_id,
        "tenant_id": "default",
        "source": "test_source",
        "thread_id": str(uuid.uuid4()),
        "msg_id": "1",
        "ts": datetime.now(timezone.utc),
        "author_raw": "author",
        "author_uuid": str(uuid.uuid4()),
        "text": "Hello world",
        "media_url": None,
        "media_type": None,
        "attrs": None,
        "pii_flags": None,
        "created_at": datetime.now(timezone.utc),
        "created_by_run": "test_run",
    }

    table = db_backend.table("messages", schema=INGESTION_MESSAGE_SCHEMA)
    table.insert([common_data])

    with pytest.raises(duckdb.ConstraintException, match="PRIMARY KEY constraint violated"):
        table.insert([common_data])
