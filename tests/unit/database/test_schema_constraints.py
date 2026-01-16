"""Tests for database schema constraints (NOT NULL, CHECK, UNIQUE, FOREIGN KEY)."""

import uuid
import duckdb
import pytest

from egregora.database.schemas import (
    POSTS_SCHEMA,
    TASKS_SCHEMA,
    create_table_if_not_exists,
    get_table_check_constraints,
    MEDIA_SCHEMA,
    ANNOTATIONS_SCHEMA,
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


class TestMediaSchemaConstraints:
    """Test constraints for the media table."""

    def test_media_media_type_check_constraint_allows_valid_values(self, duckdb_conn):
        """Verify that media.media_type CHECK constraint allows valid media types."""
        # Arrange
        constraints = get_table_check_constraints("media")
        create_table_if_not_exists(duckdb_conn, "media", MEDIA_SCHEMA, check_constraints=constraints)

        # Act & Assert
        valid_media_types = ["image", "video", "audio"]
        for media_type in valid_media_types:
            duckdb_conn.execute(
                """
                INSERT INTO media (id, content, created_at, source_checksum,
                                   filename, mime_type, media_type, phash)
                VALUES (?, 'content', CURRENT_TIMESTAMP, 'checksum',
                        'file.jpg', 'image/jpeg', ?, 'phash')
                """,
                (f"media-{media_type}", media_type),
            )

        result = duckdb_conn.execute("SELECT COUNT(*) FROM media").fetchone()
        assert result[0] == len(valid_media_types)

    def test_media_media_type_check_constraint_rejects_invalid_values(self, duckdb_conn):
        """Verify that media.media_type CHECK constraint rejects invalid media types."""
        # Arrange
        constraints = get_table_check_constraints("media")
        create_table_if_not_exists(duckdb_conn, "media", MEDIA_SCHEMA, check_constraints=constraints)

        # Act & Assert
        invalid_media_types = ["banana", "IMAGE", ""]
        for media_type in invalid_media_types:
            with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
                duckdb_conn.execute(
                    """
                    INSERT INTO media (id, content, created_at, source_checksum,
                                       filename, mime_type, media_type, phash)
                    VALUES (?, 'content', CURRENT_TIMESTAMP, 'checksum',
                            'file.jpg', 'image/jpeg', ?, 'phash')
                    """,
                    (f"media-{media_type}", media_type),
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
