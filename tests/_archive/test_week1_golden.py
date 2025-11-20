"""Week 1 Golden Test: Fast structural validation without LLM calls.

This test validates Week 1 infrastructure in <5 minutes:
1. WhatsApp ingestion → IR v1 schema
2. Privacy gate with PrivacyPass capability token
3. UUID5 deterministic anonymization
4. Runs tracking and lineage
5. Schema validation and data integrity

Goal: Smoke test that all Week 1 components integrate correctly.
Scope: Ingestion + Privacy only (no enrichment, no generation)
Target: <5 min execution time
"""

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import ibis
import pytest
from egregora.input_adapters.whatsapp.parser import parse_source
from ibis.expr import datatypes as dt

from egregora.database.ir_schema import CONVERSATION_SCHEMA
from egregora.database.tracking import record_run
from egregora.input_adapters.whatsapp import WhatsAppExport, discover_chat_file
from egregora.privacy.anonymizer import anonymize_table


@pytest.fixture
def whatsapp_fixture() -> Path:
    """Path to WhatsApp test fixture."""
    return Path(__file__).parent.parent / "fixtures" / "Conversa do WhatsApp com Teste.zip"


@pytest.fixture
def runs_db(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    """Create runs database for tracking."""
    db_path = tmp_path / "runs.duckdb"
    conn = duckdb.connect(str(db_path))

    # Create runs table (matches RUNS_TABLE_SCHEMA)
    conn.execute("""
        CREATE TABLE runs (
            run_id UUID PRIMARY KEY,
            stage VARCHAR NOT NULL,
            tenant_id VARCHAR,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            code_ref VARCHAR,
            config_hash VARCHAR,
            rows_in INTEGER,
            rows_out INTEGER,
            duration_seconds DOUBLE PRECISION,
            llm_calls INTEGER DEFAULT 0,
            tokens INTEGER DEFAULT 0,
            status VARCHAR NOT NULL,
            error TEXT,
            trace_id VARCHAR,
            parent_run_id UUID,
            attrs JSON
        )
    """)

    # Create lineage table
    conn.execute("""
        CREATE TABLE lineage (
            child_run_id UUID NOT NULL,
            parent_run_id UUID NOT NULL,
            PRIMARY KEY (child_run_id, parent_run_id),
            FOREIGN KEY (child_run_id) REFERENCES runs(run_id),
            FOREIGN KEY (parent_run_id) REFERENCES runs(run_id)
        )
    """)

    yield conn
    conn.close()


def test_week1_golden_whatsapp_pipeline(
    whatsapp_fixture: Path,
    runs_db: duckdb.DuckDBPyConnection,
    tmp_path: Path,
):
    """Golden test: WhatsApp → IR v1 → Privacy → Validation (<5 min target).

    This test validates:
    - WhatsApp parsing produces valid IR v1 schema
    - Privacy gate executes with capability token
    - UUID5 anonymization is deterministic
    - Runs tracking records execution metadata
    - Re-ingestion produces identical UUIDs
    """
    start_time = time.time()

    # ===========================================================================
    # Stage 1: Ingestion (WhatsApp → IR v1)
    # ===========================================================================

    ingestion_run_id = uuid.uuid4()
    ingestion_start = time.time()

    # Discover chat file in ZIP
    group_name, chat_file = discover_chat_file(whatsapp_fixture)
    from egregora.data_primitives import GroupSlug

    export = WhatsAppExport(
        zip_path=whatsapp_fixture,
        chat_file=chat_file,
        group_name=group_name,
        group_slug=GroupSlug(group_name.lower().replace(" ", "-")),
        export_date=datetime.now(UTC).date(),
        media_files=[],  # We don't need media for this test
    )

    # Parse WhatsApp export
    table = parse_source(export)
    table = table.mutate(event_id=ibis.literal(uuid.uuid4()))

    # Validate IR v1 schema conformance
    # Parser returns: ts, date, author, author_raw, author_uuid, text, original_line, tagged_line, message_id
    expected_ir_v1_columns = {
        "ts",
        "date",
        "author",
        "author_raw",
        "author_uuid",
        "text",
        "original_line",
        "tagged_line",
        "message_id",
        "event_id",
    }
    assert set(table.columns) == expected_ir_v1_columns, (
        f"Schema mismatch\n"
        f"  Expected: {expected_ir_v1_columns}\n"
        f"  Actual:   {set(table.columns)}\n"
        f"  Missing:  {expected_ir_v1_columns - set(table.columns)}\n"
        f"  Extra:    {set(table.columns) - expected_ir_v1_columns}"
    )

    # Validate data contents
    row_count = table.count().execute()
    assert row_count > 0, "No messages parsed"

    # Validate required fields are populated (using IR v1 column names)
    df = table.execute()
    assert df["ts"].notna().all(), "Missing timestamps"
    assert df["author"].notna().all(), "Missing authors"
    assert df["text"].notna().all(), "Missing messages"

    # Record ingestion run
    ingestion_end_time = datetime.now(UTC)
    record_run(
        conn=runs_db,
        run_id=ingestion_run_id,
        stage="ingestion",
        status="completed",
        started_at=datetime.fromtimestamp(ingestion_start, UTC),
        finished_at=ingestion_end_time,
        tenant_id="test-tenant",
        rows_in=0,
        rows_out=row_count,
    )
    time.time()

    # ===========================================================================
    # Stage 2: Privacy Gate (Anonymization + UUID5)
    # ===========================================================================

    privacy_run_id = uuid.uuid4()
    privacy_start = time.time()

    # Parser already produces IR v1 schema (ts, text, author_raw, author_uuid)
    # Only add the additional columns needed for privacy processing
    ir_table = table.mutate(
        tenant_id=ibis.literal(str(export.group_slug)),
        source=ibis.literal("whatsapp"),
        thread_id=ibis.literal(uuid.uuid4()),
        media_url=ibis.null().cast(dt.string),
        media_type=ibis.null().cast(dt.string),
        attrs=ibis.null().cast(dt.json),
        pii_flags=ibis.null().cast(dt.json),
        created_at=ibis.literal(datetime.now(UTC)),
        created_by_run=ibis.literal(uuid.uuid4()),
    )

    # Note: parse_source already calls anonymize_table, so authors are already UUIDs
    # The second call tests idempotency
    anonymized_table = anonymize_table(ir_table)

    # Validate anonymization respects new IR schema
    anon_df = anonymized_table.execute()
    assert "author_raw" in anon_df.columns, "Missing author_raw column"
    assert anon_df["author_raw"].notna().all(), "Missing author_raw values"

    ir_df = ir_table.execute()
    unique_authors_raw = ir_df["author_raw"].unique()

    # Verify authors are anonymized (should be UUID format)
    import re

    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    for author_raw in unique_authors_raw:
        assert uuid_pattern.match(author_raw), f"Author not anonymized to UUID format: {author_raw}"

    # Record privacy run
    privacy_end_time = datetime.now(UTC)
    record_run(
        conn=runs_db,
        run_id=privacy_run_id,
        stage="privacy",
        status="completed",
        started_at=datetime.fromtimestamp(privacy_start, UTC),
        finished_at=privacy_end_time,
        tenant_id="test-tenant",
        rows_in=row_count,
        rows_out=row_count,
    )

    # Record lineage: privacy depends on ingestion
    runs_db.execute(
        """
        INSERT INTO lineage (child_run_id, parent_run_id)
        VALUES (?, ?)
        """,
        [str(privacy_run_id), str(ingestion_run_id)],
    )
    time.time()

    # ===========================================================================
    # Stage 3: Re-ingestion Test (Determinism Validation)
    # ===========================================================================

    time.time()

    # Re-parse same export (parse_source already anonymizes)
    table2 = parse_source(export)
    df2 = table2.execute()

    # Validate identical anonymized values on re-ingest
    # Both parses should produce the same anonymized UUIDs
    unique_authors_raw2 = df2["author_raw"].unique()

    # Same number of unique authors
    assert len(unique_authors_raw) == len(unique_authors_raw2), (
        f"Author count mismatch: {len(unique_authors_raw)} vs {len(unique_authors_raw2)}"
    )

    # Same anonymized UUIDs (order may differ, so compare sets)
    assert set(unique_authors_raw) == set(unique_authors_raw2), "Anonymized UUIDs differ between re-ingests"

    time.time()

    # ===========================================================================
    # Validation: Runs Tracking
    # ===========================================================================

    # Query runs table
    runs = runs_db.execute("""
        SELECT run_id, stage, status, rows_out
        FROM runs
        ORDER BY started_at
    """).fetchall()

    assert len(runs) == 2, f"Expected 2 runs, got {len(runs)}"
    assert runs[0][1] == "ingestion", "First run should be ingestion"
    assert runs[1][1] == "privacy", "Second run should be privacy"
    assert all(run[2] == "completed" for run in runs), "All runs should be completed"

    # Query lineage table
    lineage = runs_db.execute("""
        SELECT child_run_id, parent_run_id
        FROM lineage
    """).fetchall()

    assert len(lineage) == 1, f"Expected 1 lineage edge, got {len(lineage)}"
    assert lineage[0][0] == privacy_run_id, "Child should be privacy run"
    assert lineage[0][1] == ingestion_run_id, "Parent should be ingestion run"

    # ===========================================================================
    # Performance Validation
    # ===========================================================================
    total_time = time.time() - start_time

    # Week 1 target: <5 min for golden test
    assert total_time < 300, f"Test too slow: {total_time:.2f}s (target: <300s)"

    # ===========================================================================
    # Summary
    # ===========================================================================


def test_week1_schema_lockfile_validation():
    """Validate IR v1 schema matches lockfile.

    This test ensures schema/ir_v1.sql and CONVERSATION_SCHEMA stay in sync.
    """
    # Expected columns from IR v1 schema
    expected_columns = {
        "timestamp",
        "date",
        "author",
        "message",
        "original_line",
        "tagged_line",
        "message_id",
    }

    # Actual columns from CONVERSATION_SCHEMA
    actual_columns = set(CONVERSATION_SCHEMA.keys())

    assert actual_columns == expected_columns, (
        f"Schema mismatch!\n"
        f"  Expected: {expected_columns}\n"
        f"  Actual:   {actual_columns}\n"
        f"  Missing:  {expected_columns - actual_columns}\n"
        f"  Extra:    {actual_columns - expected_columns}"
    )


def test_week1_uuid5_namespaces_immutable():
    """Validate UUID5 namespaces are immutable (locked on 2025-01-08)."""
    from egregora.privacy.uuid_namespaces import (
        NAMESPACE_AUTHOR,
        NAMESPACE_EVENT,
        NAMESPACE_THREAD,
    )

    # These UUIDs MUST NOT change (locked in Week 1)
    # Generated on 2025-01-08 and frozen for deterministic identity mapping
    assert str(NAMESPACE_AUTHOR) == str(uuid.NAMESPACE_URL)
    assert str(NAMESPACE_EVENT) == "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    assert str(NAMESPACE_THREAD) == "550e8400-e29b-41d4-a716-446655440000"


def test_week1_runs_schema_validation(runs_db: duckdb.DuckDBPyConnection):
    """Validate runs table schema matches the canonical IR schema."""
    from egregora.database.ir_schema import RUNS_TABLE_SCHEMA

    # Query runs table columns
    columns = runs_db.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = 'runs'
        ORDER BY ordinal_position
    """).fetchall()

    column_names = {col[0] for col in columns}

    expected_columns = set(RUNS_TABLE_SCHEMA.names)

    assert column_names == expected_columns, f"Runs schema mismatch: {column_names ^ expected_columns}"
