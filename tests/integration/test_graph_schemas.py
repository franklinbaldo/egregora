"""Integration test for Graph / Knowledge Base schemas (RFC 042/043)."""

from datetime import UTC, datetime

import duckdb
import pytest

from egregora.database.init import initialize_database


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


def test_graph_tables_and_indexes_created(duckdb_conn):
    """Verify that document_relations and entity_aliases tables and their indexes are created."""
    # Act
    initialize_database(duckdb_conn)

    # Assert Tables
    result = duckdb_conn.execute("SHOW TABLES").fetchall()
    tables = {row[0] for row in result}
    assert "document_relations" in tables
    assert "entity_aliases" in tables

    # Assert Indexes on document_relations
    result_rels = duckdb_conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'document_relations'"
    ).fetchall()
    indexes_rels = {row[0] for row in result_rels}
    assert "idx_doc_rels_source" in indexes_rels
    assert "idx_doc_rels_target" in indexes_rels
    assert "idx_doc_rels_source_target" in indexes_rels
    assert "idx_doc_rels_target_type" in indexes_rels

    # Assert Indexes on entity_aliases
    result_aliases = duckdb_conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'entity_aliases'"
    ).fetchall()
    indexes_aliases = {row[0] for row in result_aliases}
    assert "idx_entity_aliases_alias" in indexes_aliases
    assert "idx_entity_aliases_target" in indexes_aliases


def test_document_relations_insertion(duckdb_conn):
    """Verify we can insert data into document_relations."""
    initialize_database(duckdb_conn)
    ts = datetime.now(UTC)

    # Insert dummy documents first (to satisfy potential FKs)
    duckdb_conn.execute(
        "INSERT INTO documents (id, doc_type, status, created_at, title, slug, source_checksum) VALUES ('doc1', 'post', 'published', ?, 'Title1', 'slug1', 'hash1')",
        [ts],
    )
    duckdb_conn.execute(
        "INSERT INTO documents (id, doc_type, status, created_at, title, subject_uuid, source_checksum) VALUES ('doc2', 'profile', 'published', ?, 'Name2', 'uuid2', 'hash2')",
        [ts],
    )

    # Insert relation
    sql = """
    INSERT INTO document_relations (source_id, target_id, relation_type, weight, created_at, metadata)
    VALUES ('doc1', 'doc2', 'mentions', 1.0, ?, '{"context": "snippet"}')
    """
    duckdb_conn.execute(sql, [ts])

    # Verify insertion
    result = duckdb_conn.execute("SELECT * FROM document_relations").fetchall()
    assert len(result) == 1
    assert result[0][0] == "doc1"
    assert result[0][1] == "doc2"
    assert result[0][2] == "mentions"


def test_document_relations_check_constraint(duckdb_conn):
    """Verify that relation_type check constraint is enforced."""
    initialize_database(duckdb_conn)
    ts = datetime.now(UTC)

    # Insert dummy documents
    duckdb_conn.execute(
        "INSERT INTO documents (id, doc_type, status, created_at, title, slug, source_checksum) VALUES ('doc1', 'post', 'published', ?, 'Title1', 'slug1', 'hash1')",
        [ts],
    )
    duckdb_conn.execute(
        "INSERT INTO documents (id, doc_type, status, created_at, title, subject_uuid, source_checksum) VALUES ('doc2', 'profile', 'published', ?, 'Name2', 'uuid2', 'hash2')",
        [ts],
    )

    # Attempt invalid relation_type
    sql = """
    INSERT INTO document_relations (source_id, target_id, relation_type, weight, created_at)
    VALUES ('doc1', 'doc2', 'INVALID_TYPE', 1.0, ?)
    """
    # DuckDB constraint violation handling
    with pytest.raises(duckdb.ConstraintException):
        duckdb_conn.execute(sql, [ts])


def test_entity_aliases_insertion(duckdb_conn):
    """Verify we can insert data into entity_aliases."""
    initialize_database(duckdb_conn)
    ts = datetime.now(UTC)

    # Insert dummy document
    duckdb_conn.execute(
        "INSERT INTO documents (id, doc_type, status, created_at, title, subject_uuid, source_checksum) VALUES ('doc_p1', 'profile', 'published', ?, 'NameP1', 'uuidP1', 'hashP1')",
        [ts],
    )

    # Insert alias
    sql = """
    INSERT INTO entity_aliases (alias, target_id, is_canonical, created_at)
    VALUES ('Mom', 'doc_p1', true, ?)
    """
    duckdb_conn.execute(sql, [ts])

    # Verify insertion
    result = duckdb_conn.execute("SELECT * FROM entity_aliases").fetchall()
    assert len(result) == 1
    assert result[0][0] == "Mom"
    assert result[0][1] == "doc_p1"
    assert result[0][2] is True
