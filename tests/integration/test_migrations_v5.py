"""Integration test for V5 PK migrations."""

import duckdb
import pytest
from datetime import datetime, timedelta

from egregora.database.schemas import (
    ASSET_CACHE_SCHEMA,
    GIT_COMMITS_SCHEMA,
    create_table_if_not_exists,
)
from egregora.database.migrations_v5_pks import migrate_add_pks

def test_migration_v5_asset_cache_pk():
    conn = duckdb.connect(":memory:")

    # 1. Setup OLD state (no PK)
    # We use create_table_if_not_exists WITHOUT PK argument
    create_table_if_not_exists(conn, "asset_cache", ASSET_CACHE_SCHEMA)

    # Verify no PK
    constraints = conn.execute(
        "SELECT constraint_type FROM duckdb_constraints() WHERE table_name='asset_cache' AND constraint_type='PRIMARY KEY'"
    ).fetchall()
    assert len(constraints) == 0

    # 2. Insert duplicate data
    now = datetime.utcnow()
    older = now - timedelta(hours=1)

    # Row 1: Older fetch
    conn.execute("""
        INSERT INTO asset_cache (url, content_hash, content_type, content, fetched_at)
        VALUES ('http://example.com', 'hash1', 'text/html', 'content1', ?)
    """, [older])

    # Row 2: Newer fetch (should survive)
    conn.execute("""
        INSERT INTO asset_cache (url, content_hash, content_type, content, fetched_at)
        VALUES ('http://example.com', 'hash2', 'text/html', 'content2', ?)
    """, [now])

    assert conn.execute("SELECT COUNT(*) FROM asset_cache").fetchone()[0] == 2

    # 3. Run Migration
    migrate_add_pks(conn)

    # 4. Verify PK
    constraints = conn.execute(
        "SELECT constraint_type FROM duckdb_constraints() WHERE table_name='asset_cache' AND constraint_type='PRIMARY KEY'"
    ).fetchall()
    assert len(constraints) > 0

    # 5. Verify Deduplication (Should keep newer)
    count = conn.execute("SELECT COUNT(*) FROM asset_cache").fetchone()[0]
    assert count == 1

    row = conn.execute("SELECT content_hash FROM asset_cache").fetchone()
    assert row[0] == 'hash2'

    # 6. Verify ID integrity constraint (try to insert duplicate)
    try:
        conn.execute("""
            INSERT INTO asset_cache (url, content_hash, content_type, content, fetched_at)
            VALUES ('http://example.com', 'hash3', 'text/html', 'content3', ?)
        """, [now])
        pytest.fail("Should have raised ConstraintException")
    except duckdb.ConstraintException:
        pass


def test_migration_v5_git_commits_pk():
    conn = duckdb.connect(":memory:")

    # 1. Setup OLD state (no PK)
    create_table_if_not_exists(conn, "git_commits", GIT_COMMITS_SCHEMA)

    # Verify no PK
    constraints = conn.execute(
        "SELECT constraint_type FROM duckdb_constraints() WHERE table_name='git_commits' AND constraint_type='PRIMARY KEY'"
    ).fetchall()
    assert len(constraints) == 0

    # 2. Insert duplicate data
    ts = datetime.utcnow()

    # Insert same row twice
    conn.execute("""
        INSERT INTO git_commits (repo_path, commit_sha, commit_timestamp, change_type)
        VALUES ('src/main.py', 'sha123', ?, 'M')
    """, [ts])

    conn.execute("""
        INSERT INTO git_commits (repo_path, commit_sha, commit_timestamp, change_type)
        VALUES ('src/main.py', 'sha123', ?, 'M')
    """, [ts])

    assert conn.execute("SELECT COUNT(*) FROM git_commits").fetchone()[0] == 2

    # 3. Run Migration
    migrate_add_pks(conn)

    # 4. Verify PK
    constraints = conn.execute(
        "SELECT constraint_type FROM duckdb_constraints() WHERE table_name='git_commits' AND constraint_type='PRIMARY KEY'"
    ).fetchall()
    assert len(constraints) > 0

    # 5. Verify Deduplication
    count = conn.execute("SELECT COUNT(*) FROM git_commits").fetchone()[0]
    assert count == 1

    # 6. Verify PK integrity (try to insert duplicate)
    try:
        conn.execute("""
            INSERT INTO git_commits (repo_path, commit_sha, commit_timestamp, change_type)
            VALUES ('src/main.py', 'sha123', ?, 'M')
        """, [ts])
        pytest.fail("Should have raised ConstraintException")
    except duckdb.ConstraintException:
        pass
