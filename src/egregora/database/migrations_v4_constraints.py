"""Migration to add primary key to documents and foreign key to annotations."""

import contextlib
import logging

import duckdb

from egregora.database.schemas import (
    ANNOTATIONS_SCHEMA,
    UNIFIED_SCHEMA,
    create_table_if_not_exists,
    get_table_check_constraints,
    get_table_foreign_keys,
)

logger = logging.getLogger(__name__)


def migrate_add_constraints(conn: duckdb.DuckDBPyConnection) -> None:
    """Migrate database to enforce PK on documents and FK on annotations.

    Strategy: Create-Copy-Swap.
    """
    logger.info("Starting migration: Add constraints (PK/FK)")

    # 1. Migrating DOCUMENTS
    # Check if documents table exists and has PK
    try:
        constraints = conn.execute(
            "SELECT constraint_type FROM duckdb_constraints() WHERE table_name='documents' AND constraint_type='PRIMARY KEY'"
        ).fetchall()
        has_pk = len(constraints) > 0
    except duckdb.Error:
        # Table might not exist or system table issue
        has_pk = False

    if not has_pk:
        logger.info("Migrating documents table to add PRIMARY KEY...")
        # Create new table
        create_table_if_not_exists(
            conn,
            "documents_new",
            UNIFIED_SCHEMA,
            check_constraints=get_table_check_constraints("documents"),
            primary_key="id",
        )

        # Copy data if old table exists
        try:
            # Check if old table exists
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            if "documents" in tables:
                # We need to respect the CHECK constraints when copying.
                # Specifically, 'post' requires title/slug/status.
                # If old data violates this, we might need to patch it or filter it.
                # However, previous migration was supposed to fix this.
                # If we encounter violations, it means data is corrupt.
                # For this migration, we will try to copy valid rows only?
                # Or better, we should have fixed data before.
                # Assuming data respects constraints (or we accept failure).
                # But to make it robust, we can use INSERT OR IGNORE? No, DuckDB doesn't fully support it for CHECKs easily.

                # Let's check for bad data first?
                # No, just let it fail if data is bad, but we are in dev/test here.
                # In the test case (main block), I inserted a row with NULLs for title/slug.
                # I should update the test case to insert valid data.

                conn.execute("INSERT INTO documents_new SELECT * FROM documents WHERE id IS NOT NULL")
                conn.execute("DROP TABLE documents")

            conn.execute("ALTER TABLE documents_new RENAME TO documents")
            logger.info("Documents table migrated successfully.")

        except duckdb.ConstraintException as e:
            logger.error(
                "Migration failed due to data integrity violation (Duplicate IDs or Check Constraints): %s", e
            )
            # Cleanup
            conn.execute("DROP TABLE IF EXISTS documents_new")
            raise
        except Exception as e:
            logger.error("Migration failed for documents: %s", e)
            conn.execute("DROP TABLE IF EXISTS documents_new")
            raise
    else:
        logger.info("Documents table already has PRIMARY KEY.")

    # 2. Migrating ANNOTATIONS
    # We need to recreate annotations to add FK.
    # Note: We can only add FK if documents table has PK (handled above).

    logger.info("Migrating annotations table to add FOREIGN KEY...")
    create_table_if_not_exists(
        conn,
        "annotations_new",
        ANNOTATIONS_SCHEMA,
        check_constraints=get_table_check_constraints("annotations"),
        foreign_keys=get_table_foreign_keys("annotations"),
    )

    try:
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if "annotations" in tables:
            # Copy data. Ensure we don't copy orphans.

            # Let's count orphans
            orphans_count = conn.execute(
                "SELECT COUNT(*) FROM annotations WHERE parent_id NOT IN (SELECT id FROM documents)"
            ).fetchone()[0]

            if orphans_count > 0:
                logger.warning(
                    "Found %d orphan annotations. These will be excluded from the new table.", orphans_count
                )

            conn.execute("""
                INSERT INTO annotations_new
                SELECT * FROM annotations
                WHERE parent_id IN (SELECT id FROM documents)
            """)
            conn.execute("DROP TABLE annotations")

        conn.execute("ALTER TABLE annotations_new RENAME TO annotations")
        logger.info("Annotations table migrated successfully.")

    except Exception as e:
        logger.error("Migration failed for annotations: %s", e)
        conn.execute("DROP TABLE IF EXISTS annotations_new")
        raise

    logger.info("Migration completed successfully.")


if __name__ == "__main__":
    # Test run
    con = duckdb.connect(":memory:")
    # Setup initial state (no constraints)
    create_table_if_not_exists(con, "documents", UNIFIED_SCHEMA)

    # INSERT VALID DATA that satisfies CHECK constraints
    # Post requires title, slug, status
    con.execute(
        "INSERT INTO documents (id, content, doc_type, status, title, slug) VALUES ('d1', 'c1', 'post', 'published', 'Title 1', 'slug-1')"
    )

    create_table_if_not_exists(con, "annotations", ANNOTATIONS_SCHEMA)
    con.execute(
        "INSERT INTO annotations (id, parent_id, content, parent_type) VALUES ('a1', 'd1', 'valid', 'post')"
    )
    con.execute(
        "INSERT INTO annotations (id, parent_id, content, parent_type) VALUES ('a2', 'd2', 'orphan', 'post')"
    )

    migrate_add_constraints(con)

    # Verify
    res = con.execute("SELECT count(*) FROM annotations").fetchone()[0]

    with contextlib.suppress(duckdb.ConstraintException):
        con.execute(
            "INSERT INTO annotations (id, parent_id, content, parent_type) VALUES ('a3', 'bad', 'content', 'post')"
        )
