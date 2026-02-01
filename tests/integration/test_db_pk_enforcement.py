import duckdb
import pytest

from egregora.database.init import initialize_database


@pytest.fixture
def db_connection():
    conn = duckdb.connect(":memory:")
    initialize_database(conn)
    return conn


def test_pk_enforcement_tasks(db_connection):
    """Verify primary key enforcement on tasks table."""
    conn = db_connection

    # Insert first record
    uuid = "12345678-1234-5678-1234-567812345678"
    conn.execute(f"""
        INSERT INTO tasks (task_id, task_type, status, payload, created_at)
        VALUES ('{uuid}', 'generate_banner', 'pending', '{{}}', CURRENT_TIMESTAMP)
    """)

    # Attempt to insert duplicate task_id
    with pytest.raises(duckdb.ConstraintException):
        conn.execute(f"""
            INSERT INTO tasks (task_id, task_type, status, payload, created_at)
            VALUES ('{uuid}', 'update_profile', 'pending', '{{}}', CURRENT_TIMESTAMP)
        """)


def test_pk_enforcement_git_commits(db_connection):
    """Verify composite primary key enforcement on git_commits table."""
    conn = db_connection

    # Insert first record
    conn.execute("""
        INSERT INTO git_commits (repo_path, commit_sha, commit_timestamp, change_type)
        VALUES ('src/main.py', 'sha123', CURRENT_TIMESTAMP, 'M')
    """)

    # Insert different file, same commit (Should pass)
    conn.execute("""
        INSERT INTO git_commits (repo_path, commit_sha, commit_timestamp, change_type)
        VALUES ('src/utils.py', 'sha123', CURRENT_TIMESTAMP, 'M')
    """)

    # Insert same file, different commit (Should pass)
    conn.execute("""
        INSERT INTO git_commits (repo_path, commit_sha, commit_timestamp, change_type)
        VALUES ('src/main.py', 'sha456', CURRENT_TIMESTAMP, 'M')
    """)

    # Insert duplicate (same file, same commit) (Should fail)
    with pytest.raises(duckdb.ConstraintException):
        conn.execute("""
            INSERT INTO git_commits (repo_path, commit_sha, commit_timestamp, change_type)
            VALUES ('src/main.py', 'sha123', CURRENT_TIMESTAMP, 'M')
        """)


def test_pk_existence_all_tables(db_connection):
    """Verify primary keys exist for all expected tables."""
    conn = db_connection

    tables_with_pk = [
        "documents",
        "tasks",
        "git_commits",
        "git_refs",
        "elo_ratings",
        "comparison_history",
        "asset_cache",
    ]

    for table in tables_with_pk:
        # Check if PK constraint exists
        # DuckDB stores this in information_schema.table_constraints
        result = conn.execute(f"""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = '{table}' AND constraint_type = 'PRIMARY KEY'
        """).fetchall()

        assert len(result) > 0, f"Table {table} should have a Primary Key"


def test_idempotent_initialization(db_connection):
    """Verify that calling initialize_database twice doesn't fail."""
    # It was called once in fixture. Call it again.
    initialize_database(db_connection)

    # Verify we can still use the DB
    db_connection.execute("SELECT count(*) FROM tasks")
