"""Tests for database schema constraints (NOT NULL, CHECK, UNIQUE, FOREIGN KEY)."""

import uuid

import duckdb

# Mock schemas that were refactored away but are needed for tests
import pytest

# Test constraints on the deprecated tables are no longer relevant as those tables are gone.
# We should test constraints on the 'documents' table instead.
# Let's import UNIFIED_SCHEMA
from egregora.database.schemas import (
    ANNOTATIONS_SCHEMA,
    STAGING_MESSAGES_SCHEMA,
    TASKS_SCHEMA,
    UNIFIED_SCHEMA,
    create_table_if_not_exists,
    get_table_check_constraints,
)


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


class TestUnifiedDocumentsSchemaConstraints:
    """Test constraints for the unified documents table."""

    def test_doc_post_check_constraint_allows_valid_values(self, duckdb_conn):
        """Verify that documents.doc_type='post' requirements are enforced."""
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints)

        # Valid Post
        duckdb_conn.execute(
            """
            INSERT INTO documents (id, doc_type, status, title, slug, content, created_at, source_checksum)
            VALUES (?, 'post', 'draft', 'Title', 'slug', 'content', CURRENT_TIMESTAMP, 'hash')
            """,
            ("post-1",),
        )

        # Assert inserted
        count = duckdb_conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        assert count == 1

    def test_doc_post_check_constraint_rejects_missing_title(self, duckdb_conn):
        """Verify that documents.doc_type='post' requires title."""
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints)

        # Invalid Post (missing title)
        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, doc_type, status, title, slug, content, created_at, source_checksum)
                VALUES (?, 'post', 'draft', NULL, 'slug', 'content', CURRENT_TIMESTAMP, 'hash')
                """,
                ("post-2",),
            )


class TestTasksSchemaConstraints:
    """Test constraints for the tasks table."""

    def test_tasks_status_check_constraint_allows_valid_values(self, duckdb_conn):
        """Verify that tasks.status CHECK constraint allows valid status values."""
        # Arrange: Create tasks table with constraints
        constraints = get_table_check_constraints("tasks")
        create_table_if_not_exists(duckdb_conn, "tasks", TASKS_SCHEMA, check_constraints=constraints)

        # Act & Assert: Valid status values should be accepted
        valid_statuses = ["pending", "processing", "completed", "failed", "superseded"]
        for status in valid_statuses:
            task_id = uuid.uuid4()
            duckdb_conn.execute(
                """
                INSERT INTO tasks (task_id, task_type, status, payload, created_at)
                VALUES (?, 'update_profile', ?, '{}', CURRENT_TIMESTAMP)
                """,
                (task_id, status),
            )

        # Verify all rows were inserted
        result = duckdb_conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
        assert result[0] == len(valid_statuses)

    def test_tasks_status_check_constraint_rejects_invalid_values(self, duckdb_conn):
        """Verify that tasks.status CHECK constraint rejects invalid status values."""
        # Arrange: Create tasks table with constraints
        constraints = get_table_check_constraints("tasks")
        create_table_if_not_exists(duckdb_conn, "tasks", TASKS_SCHEMA, check_constraints=constraints)

        # Act & Assert: Invalid status values should be rejected
        invalid_statuses = ["banana", "PENDING", "Completed", "", "unknown"]
        for invalid_status in invalid_statuses:
            task_id = uuid.uuid4()
            with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
                duckdb_conn.execute(
                    """
                    INSERT INTO tasks (task_id, task_type, status, payload, created_at)
                    VALUES (?, 'update_profile', ?, '{}', CURRENT_TIMESTAMP)
                    """,
                    (task_id, invalid_status),
                )

    def test_tasks_task_type_check_constraint_allows_valid_values(self, duckdb_conn):
        """Verify that tasks.task_type CHECK constraint allows valid task types."""
        # Arrange
        constraints = get_table_check_constraints("tasks")
        create_table_if_not_exists(duckdb_conn, "tasks", TASKS_SCHEMA, check_constraints=constraints)

        # Act & Assert
        valid_task_types = ["generate_banner", "update_profile", "enrich_media"]
        for task_type in valid_task_types:
            task_id = uuid.uuid4()
            duckdb_conn.execute(
                """
                INSERT INTO tasks (task_id, task_type, status, payload, created_at)
                VALUES (?, ?, 'pending', '{}', CURRENT_TIMESTAMP)
                """,
                (task_id, task_type),
            )

        result = duckdb_conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
        assert result[0] == len(valid_task_types)

    def test_tasks_task_type_check_constraint_rejects_invalid_values(self, duckdb_conn):
        """Verify that tasks.task_type CHECK constraint rejects invalid task types."""
        # Arrange
        constraints = get_table_check_constraints("tasks")
        create_table_if_not_exists(duckdb_conn, "tasks", TASKS_SCHEMA, check_constraints=constraints)

        # Act & Assert
        invalid_task_types = ["banana", "GENERATE_BANNER", ""]
        for task_type in invalid_task_types:
            task_id = uuid.uuid4()
            with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
                duckdb_conn.execute(
                    """
                    INSERT INTO tasks (task_id, task_type, status, payload, created_at)
                    VALUES (?, ?, 'pending', '{}', CURRENT_TIMESTAMP)
                    """,
                    (task_id, task_type),
                )


class TestAnnotationsSchemaConstraints:
    """Test constraints for the annotations table."""

    def test_annotations_parent_type_check_constraint_allows_valid_values(self, duckdb_conn):
        """Verify that annotations.parent_type CHECK constraint allows valid parent types."""
        # Arrange
        constraints = get_table_check_constraints("annotations")
        create_table_if_not_exists(
            duckdb_conn, "annotations", ANNOTATIONS_SCHEMA, check_constraints=constraints
        )

        # Act & Assert
        valid_parent_types = ["message", "post", "annotation"]
        for parent_type in valid_parent_types:
            duckdb_conn.execute(
                """
                INSERT INTO annotations (id, content, created_at, source_checksum,
                                         parent_id, parent_type, author_id)
                VALUES (?, 'content', CURRENT_TIMESTAMP, 'checksum',
                        'parent1', ?, 'author1')
                """,
                (f"anno-{parent_type}", parent_type),
            )

        result = duckdb_conn.execute("SELECT COUNT(*) FROM annotations").fetchone()
        assert result[0] == len(valid_parent_types)

    def test_annotations_parent_type_check_constraint_rejects_invalid_values(self, duckdb_conn):
        """Verify that annotations.parent_type CHECK constraint rejects invalid parent types."""
        # Arrange
        constraints = get_table_check_constraints("annotations")
        create_table_if_not_exists(
            duckdb_conn, "annotations", ANNOTATIONS_SCHEMA, check_constraints=constraints
        )

        # Act & Assert
        invalid_parent_types = ["banana", "POST", ""]
        for parent_type in invalid_parent_types:
            with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
                duckdb_conn.execute(
                    """
                    INSERT INTO annotations (id, content, created_at, source_checksum,
                                             parent_id, parent_type, author_id)
                    VALUES (?, 'content', CURRENT_TIMESTAMP, 'checksum',
                            'parent1', ?, 'author1')
                    """,
                    (f"anno-{parent_type}", parent_type),
                )


class TestMessagesSchemaConstraints:
    """Test constraints for the messages (staging) table."""

    def test_messages_media_type_allows_valid_values_or_null(self, duckdb_conn):
        """Verify that messages.media_type allows valid types or NULL."""
        # Arrange
        constraints = get_table_check_constraints("messages")
        create_table_if_not_exists(
            duckdb_conn, "messages", STAGING_MESSAGES_SCHEMA, check_constraints=constraints
        )

        # Act & Assert
        valid_inputs = ["image", "video", "audio", None]
        for i, media_type in enumerate(valid_inputs):
            duckdb_conn.execute(
                """
                INSERT INTO messages (event_id, ts, created_at, media_type)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
                """,
                (f"msg-{i}", media_type),
            )

        count = duckdb_conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        assert count == len(valid_inputs)

    def test_messages_media_type_rejects_invalid_values(self, duckdb_conn):
        """Verify that messages.media_type rejects invalid types."""
        # Arrange
        constraints = get_table_check_constraints("messages")
        create_table_if_not_exists(
            duckdb_conn, "messages", STAGING_MESSAGES_SCHEMA, check_constraints=constraints
        )

        # Act & Assert
        invalid_inputs = ["text", "IMAGE", ""]
        for i, media_type in enumerate(invalid_inputs):
            with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
                duckdb_conn.execute(
                    """
                    INSERT INTO messages (event_id, ts, created_at, media_type)
                    VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
                    """,
                    (f"msg-invalid-{i}", media_type),
                )
