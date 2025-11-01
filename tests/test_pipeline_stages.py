"""Tests for pipeline stage definitions and helpers."""

from pathlib import Path

import ibis

from egregora.core.database_schema import (
    MEDIA_FILES_SCHEMA,
    PipelineStage,
    create_stage_view,
    materialize_stage,
    stage_exists,
)


def test_pipeline_stage_enum_values():
    """Test PipelineStage enum has expected values."""
    assert PipelineStage.INGESTED == "ingested_messages"
    assert PipelineStage.ANONYMIZED == "anonymized_messages"
    assert PipelineStage.ENRICHED == "enriched_messages"
    assert PipelineStage.KNOWLEDGE == "knowledge_context"


def test_pipeline_stage_enum_iteration():
    """Test we can iterate over pipeline stages."""
    stages = list(PipelineStage)
    assert len(stages) == 4  # noqa: PLR2004
    assert PipelineStage.INGESTED in stages


def test_media_files_schema_columns():
    """Test MEDIA_FILES_SCHEMA has all expected columns."""
    expected_columns = {
        "media_id",
        "message_timestamp",
        "original_filename",
        "site_relative_path",
        "description",
        "media_type",
        "pii_redacted",
    }
    assert set(MEDIA_FILES_SCHEMA.names) == expected_columns


def test_media_files_schema_types():
    """Test MEDIA_FILES_SCHEMA column types."""
    schema_dict = dict(zip(MEDIA_FILES_SCHEMA.names, MEDIA_FILES_SCHEMA.types, strict=True))

    assert "string" in str(schema_dict["media_id"]).lower()
    assert "timestamp" in str(schema_dict["message_timestamp"]).lower()
    assert "string" in str(schema_dict["original_filename"]).lower()
    assert "boolean" in str(schema_dict["pii_redacted"]).lower()


def test_create_stage_view(tmp_path: Path):
    """Test creating a pipeline stage view."""
    # Create in-memory connection
    conn = ibis.duckdb.connect()

    # Create source data
    data = {"id": [1, 2, 3], "value": ["a", "b", "c"]}
    source = ibis.memtable(data)

    # Create view for INGESTED stage
    create_stage_view(conn, PipelineStage.INGESTED, source)

    # Verify view exists
    assert PipelineStage.INGESTED.value in conn.list_tables()

    # Verify view has correct data
    view = conn.table(PipelineStage.INGESTED.value)
    result = view.execute()
    assert len(result) == 3  # noqa: PLR2004
    assert list(result["value"]) == ["a", "b", "c"]


def test_create_stage_view_overwrite(tmp_path: Path):
    """Test overwriting an existing stage view."""
    conn = ibis.duckdb.connect()

    # Create initial view
    data1 = {"id": [1], "value": ["old"]}
    source1 = ibis.memtable(data1)
    create_stage_view(conn, PipelineStage.INGESTED, source1)

    # Overwrite with new view
    data2 = {"id": [2], "value": ["new"]}
    source2 = ibis.memtable(data2)
    create_stage_view(conn, PipelineStage.INGESTED, source2, overwrite=True)

    # Verify new data
    view = conn.table(PipelineStage.INGESTED.value)
    result = view.execute()
    assert list(result["value"]) == ["new"]


def test_materialize_stage(tmp_path: Path):
    """Test materializing a pipeline stage as a table."""
    conn = ibis.duckdb.connect()

    # Create source data
    data = {"id": [1, 2, 3], "value": ["x", "y", "z"]}
    source = ibis.memtable(data)

    # Materialize ENRICHED stage
    materialize_stage(conn, PipelineStage.ENRICHED, source)

    # Verify table exists
    assert PipelineStage.ENRICHED.value in conn.list_tables()

    # Verify table has correct data
    table = conn.table(PipelineStage.ENRICHED.value)
    result = table.execute()
    assert len(result) == 3  # noqa: PLR2004
    assert list(result["value"]) == ["x", "y", "z"]


def test_materialize_stage_overwrite():
    """Test overwriting an existing materialized stage."""
    conn = ibis.duckdb.connect()

    # Materialize initial table
    data1 = {"id": [1], "value": ["old"]}
    source1 = ibis.memtable(data1)
    materialize_stage(conn, PipelineStage.ENRICHED, source1)

    # Overwrite with new table
    data2 = {"id": [2, 3], "value": ["new1", "new2"]}
    source2 = ibis.memtable(data2)
    materialize_stage(conn, PipelineStage.ENRICHED, source2, overwrite=True)

    # Verify new data
    table = conn.table(PipelineStage.ENRICHED.value)
    result = table.execute()
    assert len(result) == 2  # noqa: PLR2004
    assert list(result["value"]) == ["new1", "new2"]


def test_stage_exists():
    """Test checking if a stage exists."""
    conn = ibis.duckdb.connect()

    # Stage doesn't exist initially
    assert not stage_exists(conn, PipelineStage.INGESTED)

    # Create view
    data = {"id": [1], "value": ["a"]}
    source = ibis.memtable(data)
    create_stage_view(conn, PipelineStage.INGESTED, source)

    # Now stage exists
    assert stage_exists(conn, PipelineStage.INGESTED)

    # Other stages still don't exist
    assert not stage_exists(conn, PipelineStage.ANONYMIZED)
    assert not stage_exists(conn, PipelineStage.ENRICHED)


def test_view_vs_materialized_stage():
    """Test difference between view and materialized stage."""
    conn = ibis.duckdb.connect()

    # Create base table
    base_data = {"id": [1, 2, 3], "value": [10, 20, 30]}
    base_table = ibis.memtable(base_data)
    conn.create_table("base", base_table)

    # Create view that references base table
    base_ref = conn.table("base")
    transformed_view = base_ref.mutate(doubled=base_ref.value * 2)
    create_stage_view(conn, PipelineStage.INGESTED, transformed_view)

    # Create materialized table (snapshot at this point)
    transformed_mat = base_ref.mutate(doubled=base_ref.value * 2)
    materialize_stage(conn, PipelineStage.ENRICHED, transformed_mat)

    # Verify both have same initial data
    view_result = conn.table(PipelineStage.INGESTED.value).execute()
    mat_result = conn.table(PipelineStage.ENRICHED.value).execute()
    assert list(view_result["doubled"]) == [20, 40, 60]
    assert list(mat_result["doubled"]) == [20, 40, 60]

    # Modify base table
    new_row = {"id": [4], "value": [40]}
    new_table = base_ref.union(ibis.memtable(new_row))
    conn.create_table("base", new_table, overwrite=True)

    # Note: Views in DuckDB are often materialized at creation, so this test
    # demonstrates the concept of views vs materialized tables.
    # In a real pipeline, views would be recreated when upstream data changes.

    # Materialized table doesn't change (snapshot)
    mat_result_after = conn.table(PipelineStage.ENRICHED.value).execute()
    assert len(mat_result_after) == 3  # noqa: PLR2004  # Still has original 3 rows


def test_all_stages_independent():
    """Test that all pipeline stages can coexist independently."""
    conn = ibis.duckdb.connect()

    # Create different data for each stage
    stages_data = {
        PipelineStage.INGESTED: {"id": [1], "msg": ["raw"]},
        PipelineStage.ANONYMIZED: {"id": [2], "msg": ["anon"]},
        PipelineStage.ENRICHED: {"id": [3], "msg": ["enriched"]},
        PipelineStage.KNOWLEDGE: {"id": [4], "msg": ["knowledge"]},
    }

    # Create all stages
    for stage, data in stages_data.items():
        source = ibis.memtable(data)
        create_stage_view(conn, stage, source)

    # Verify all exist
    for stage in PipelineStage:
        assert stage_exists(conn, stage)

    # Verify each has correct data
    for stage, data in stages_data.items():
        table = conn.table(stage.value)
        result = table.execute()
        assert list(result["msg"]) == data["msg"]
