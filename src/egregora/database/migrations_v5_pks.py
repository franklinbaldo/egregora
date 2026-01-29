"""Migration to add primary keys to asset_cache and git_commits tables.

This migration addresses the "Structure Before Scale" requirement by enforcing
primary keys on tables that were previously lacking them.

Tables affected:
- asset_cache: PK added to 'url'
- git_commits: PK added to 'repo_path', 'commit_sha'
"""

import logging

import duckdb

from egregora.database.schemas import (
    ASSET_CACHE_SCHEMA,
    GIT_COMMITS_SCHEMA,
    create_table_if_not_exists,
)

logger = logging.getLogger(__name__)


def migrate_add_pks(conn: duckdb.DuckDBPyConnection) -> None:
    """Migrate database to enforce PK on asset_cache and git_commits.

    Strategy: Create-Copy-Swap.
    """
    logger.info("Starting migration: Add Primary Keys to asset_cache and git_commits")

    _migrate_asset_cache(conn)
    _migrate_git_commits(conn)

    logger.info("Migration completed successfully.")


def _migrate_asset_cache(conn: duckdb.DuckDBPyConnection) -> None:
    """Migrate asset_cache table."""
    try:
        constraints = conn.execute(
            "SELECT constraint_type FROM duckdb_constraints() WHERE table_name='asset_cache' AND constraint_type='PRIMARY KEY'"
        ).fetchall()
        has_pk = len(constraints) > 0
    except duckdb.Error:
        # Table might not exist
        has_pk = False

    if not has_pk:
        logger.info("Migrating asset_cache table to add PRIMARY KEY...")

        # Check if table exists
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if "asset_cache" not in tables:
            logger.info("Table asset_cache does not exist. Creating new.")
            create_table_if_not_exists(conn, "asset_cache", ASSET_CACHE_SCHEMA, primary_key="url")
            return

        # Create new table
        create_table_if_not_exists(
            conn,
            "asset_cache_new",
            ASSET_CACHE_SCHEMA,
            primary_key="url",
        )

        try:
            logger.info("Copying data to asset_cache_new (deduplicating by url)...")
            # Deduplicate by URL, keeping the most recently fetched one
            conn.execute("""
                INSERT INTO asset_cache_new
                SELECT * FROM asset_cache
                QUALIFY ROW_NUMBER() OVER (PARTITION BY url ORDER BY fetched_at DESC) = 1
            """)

            conn.execute("DROP TABLE asset_cache")
            conn.execute("ALTER TABLE asset_cache_new RENAME TO asset_cache")
            logger.info("asset_cache table migrated successfully.")

        except Exception as e:
            logger.error("Migration failed for asset_cache: %s", e)
            conn.execute("DROP TABLE IF EXISTS asset_cache_new")
            raise
    else:
        logger.info("asset_cache table already has PRIMARY KEY.")


def _migrate_git_commits(conn: duckdb.DuckDBPyConnection) -> None:
    """Migrate git_commits table."""
    try:
        constraints = conn.execute(
            "SELECT constraint_type FROM duckdb_constraints() WHERE table_name='git_commits' AND constraint_type='PRIMARY KEY'"
        ).fetchall()
        has_pk = len(constraints) > 0
    except duckdb.Error:
        has_pk = False

    if not has_pk:
        logger.info("Migrating git_commits table to add PRIMARY KEY...")

        # Check if table exists
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if "git_commits" not in tables:
             logger.info("Table git_commits does not exist. Creating new.")
             create_table_if_not_exists(conn, "git_commits", GIT_COMMITS_SCHEMA, primary_key=["repo_path", "commit_sha"])
             return

        # Create new table
        create_table_if_not_exists(
            conn,
            "git_commits_new",
            GIT_COMMITS_SCHEMA,
            primary_key=["repo_path", "commit_sha"],
        )

        try:
            logger.info("Copying data to git_commits_new (deduplicating by repo_path, commit_sha)...")

            # Ensure schema compatibility (in case old table lacks new columns like stats)
            # But here we rely on standard Ibis schema.
            # If old table has missing columns, INSERT might fail if strict.
            # DuckDB is lenient with missing columns if names match? No.
            # We assume columns match or we rely on 'SELECT *' to match schema order if strict,
            # but Ibis defines schema order.

            # Handle potential schema evolution issues (missing columns in old table)
            # The easiest way is to select specific columns if we know them, but Ibis schema is dynamic.
            # Let's rely on DuckDB's flexibility or strictness.
            # If the old table lacks columns defined in GIT_COMMITS_SCHEMA, we might have an issue.
            # However, init.py adds columns 'change_type' and 'stats' if missing.
            # So we assume the table structure is up to date regarding columns.

            # Deduplicate by repo_path and commit_sha
            conn.execute("""
                INSERT INTO git_commits_new
                SELECT * FROM git_commits
                QUALIFY ROW_NUMBER() OVER (PARTITION BY repo_path, commit_sha ORDER BY commit_timestamp DESC) = 1
            """)

            conn.execute("DROP TABLE git_commits")
            conn.execute("ALTER TABLE git_commits_new RENAME TO git_commits")
            logger.info("git_commits table migrated successfully.")

        except Exception as e:
            logger.error("Migration failed for git_commits: %s", e)
            conn.execute("DROP TABLE IF EXISTS git_commits_new")
            raise
    else:
        logger.info("git_commits table already has PRIMARY KEY.")
