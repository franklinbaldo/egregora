"""Tests for database schema constraints (NOT NULL, CHECK, UNIQUE, FOREIGN KEY)."""

import pytest
import duckdb

from egregora.database.schemas import (
    create_table_if_not_exists,
    get_table_check_constraints,
    POSTS_SCHEMA,
    TASKS_SCHEMA,
)


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


class TestPostsSchemaConstraints:
    """Test constraints for the posts table."""

    def test_posts_status_check_constraint_allows_valid_values(self, duckdb_conn):
        """Verify that posts.status CHECK constraint allows valid status values."""
        # Arrange: Create posts table with constraints
        constraints = get_table_check_constraints("posts")
        create_table_if_not_exists(duckdb_conn, "posts", POSTS_SCHEMA, check_constraints=constraints)

        # Act & Assert: Valid status values should be accepted
        valid_statuses = ["draft", "published", "archived"]
        for status in valid_statuses:
            duckdb_conn.execute(
                """
                INSERT INTO posts (id, content, created_at, source_checksum,
                                  title, slug, date, summary, authors, tags, status)
                VALUES (?, 'test content', CURRENT_TIMESTAMP, 'checksum',
                       'Test Title', 'test-slug', CURRENT_DATE, 'Test summary',
                       ARRAY['author1'], ARRAY['tag1'], ?)
                """,
                (f"post-{status}", status),
            )

        # Verify all rows were inserted
        result = duckdb_conn.execute("SELECT COUNT(*) FROM posts").fetchone()
        assert result[0] == len(valid_statuses)

    def test_posts_status_check_constraint_rejects_invalid_values(self, duckdb_conn):
        """Verify that posts.status CHECK constraint rejects invalid status values."""
        # Arrange: Create posts table with constraints
        constraints = get_table_check_constraints("posts")
        create_table_if_not_exists(duckdb_conn, "posts", POSTS_SCHEMA, check_constraints=constraints)

        # Act & Assert: Invalid status values should be rejected
        invalid_statuses = ["banana", "PUBLISHED", "Draft", "", "pending"]
        for invalid_status in invalid_statuses:
            with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
                duckdb_conn.execute(
                    """
                    INSERT INTO posts (id, content, created_at, source_checksum,
                                      title, slug, date, summary, authors, tags, status)
                    VALUES (?, 'test content', CURRENT_TIMESTAMP, 'checksum',
                           'Test Title', 'test-slug', CURRENT_DATE, 'Test summary',
                           ARRAY['author1'], ARRAY['tag1'], ?)
                    """,
                    (f"post-{invalid_status}", invalid_status),
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
            task_id = f"550e8400-e29b-41d4-a716-44665544000{valid_statuses.index(status)}"
            duckdb_conn.execute(
                """
                INSERT INTO tasks (task_id, task_type, status, payload, created_at)
                VALUES (?, 'test_task', ?, '{}', CURRENT_TIMESTAMP)
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
        for idx, invalid_status in enumerate(invalid_statuses):
            task_id = f"550e8400-e29b-41d4-a716-44665544100{idx}"
            with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
                duckdb_conn.execute(
                    """
                    INSERT INTO tasks (task_id, task_type, status, payload, created_at)
                    VALUES (?, 'test_task', ?, '{}', CURRENT_TIMESTAMP)
                    """,
                    (task_id, invalid_status),
                )
