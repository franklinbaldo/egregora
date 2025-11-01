"""Tests for DAG-based pipeline orchestration."""

import ibis

from egregora.core.database_schema import PipelineStage
from egregora.orchestration.dag import (
    DAGExecutor,
    StageDependency,
    build_pipeline_dag,
)


def test_stage_dependency_creation():
    """Test creating a stage dependency."""
    dep = StageDependency(
        stage=PipelineStage.INGESTED,
        depends_on=[],
        materialized=False,
    )

    assert dep.stage == PipelineStage.INGESTED
    assert dep.depends_on == []
    assert dep.materialized is False


def test_topological_sort_linear():
    """Test topological sort with linear dependencies."""
    conn = ibis.duckdb.connect()

    # Create linear DAG: A -> B -> C
    def compute_a(conn, upstream):
        return ibis.memtable({"id": [1], "value": ["a"]})

    def compute_b(conn, upstream):
        a = upstream[PipelineStage.INGESTED]
        return a.mutate(stage=ibis.literal("b"))

    def compute_c(conn, upstream):
        b = upstream[PipelineStage.ANONYMIZED]
        return b.mutate(final=ibis.literal("c"))

    dag = [
        StageDependency(PipelineStage.INGESTED, [], False, compute_a),
        StageDependency(PipelineStage.ANONYMIZED, [PipelineStage.INGESTED], False, compute_b),
        StageDependency(PipelineStage.ENRICHED, [PipelineStage.ANONYMIZED], False, compute_c),
    ]

    executor = DAGExecutor(conn, dag)
    results = executor.execute_to_stage(PipelineStage.ENRICHED)

    # Should execute in order: INGESTED, ANONYMIZED, ENRICHED
    assert len(results) == 3  # noqa: PLR2004
    assert results[0].stage == PipelineStage.INGESTED
    assert results[1].stage == PipelineStage.ANONYMIZED
    assert results[2].stage == PipelineStage.ENRICHED


def test_topological_sort_diamond():
    """Test topological sort with diamond dependencies."""
    conn = ibis.duckdb.connect()

    # Create diamond DAG:
    #     A
    #    / \
    #   B   C
    #    \ /
    #     D

    def compute_a(conn, upstream):
        return ibis.memtable({"id": [1], "value": ["a"]})

    def compute_b(conn, upstream):
        return upstream[PipelineStage.INGESTED].mutate(branch=ibis.literal("b"))

    def compute_c(conn, upstream):
        return upstream[PipelineStage.INGESTED].mutate(branch=ibis.literal("c"))

    def compute_d(conn, upstream):
        # Depends on both B and C
        b = upstream[PipelineStage.ANONYMIZED]
        return b.mutate(merged=ibis.literal("bc"))

    dag = [
        StageDependency(PipelineStage.INGESTED, [], False, compute_a),
        StageDependency(PipelineStage.ANONYMIZED, [PipelineStage.INGESTED], False, compute_b),
        StageDependency(PipelineStage.ENRICHED, [PipelineStage.INGESTED], False, compute_c),
        StageDependency(
            PipelineStage.KNOWLEDGE,
            [PipelineStage.ANONYMIZED, PipelineStage.ENRICHED],
            False,
            compute_d,
        ),
    ]

    executor = DAGExecutor(conn, dag)
    results = executor.execute_to_stage(PipelineStage.KNOWLEDGE)

    # A must come first, D must come last, B and C can be in any order
    assert results[0].stage == PipelineStage.INGESTED
    assert results[-1].stage == PipelineStage.KNOWLEDGE
    assert len(results) == 4  # noqa: PLR2004


def test_execute_partial_dag():
    """Test executing only part of the DAG."""
    conn = ibis.duckdb.connect()

    def compute_a(conn, upstream):
        return ibis.memtable({"id": [1], "value": ["a"]})

    def compute_b(conn, upstream):
        return upstream[PipelineStage.INGESTED].mutate(value="b")

    def compute_c(conn, upstream):
        return upstream[PipelineStage.ANONYMIZED].mutate(value="c")

    dag = [
        StageDependency(PipelineStage.INGESTED, [], False, compute_a),
        StageDependency(PipelineStage.ANONYMIZED, [PipelineStage.INGESTED], False, compute_b),
        StageDependency(PipelineStage.ENRICHED, [PipelineStage.ANONYMIZED], False, compute_c),
    ]

    executor = DAGExecutor(conn, dag)

    # Execute only up to ANONYMIZED
    results = executor.execute_to_stage(PipelineStage.ANONYMIZED)

    # Should only execute INGESTED and ANONYMIZED
    assert len(results) == 2  # noqa: PLR2004
    assert results[0].stage == PipelineStage.INGESTED
    assert results[1].stage == PipelineStage.ANONYMIZED


def test_caching_behavior():
    """Test that cached stages are not recomputed."""
    conn = ibis.duckdb.connect()

    call_count = {"a": 0, "b": 0}

    def compute_a(conn, upstream):
        call_count["a"] += 1
        return ibis.memtable({"id": [1], "value": ["a"]})

    def compute_b(conn, upstream):
        call_count["b"] += 1
        return upstream[PipelineStage.INGESTED].mutate(stage=ibis.literal("b"))

    dag = [
        StageDependency(PipelineStage.INGESTED, [], False, compute_a),
        StageDependency(PipelineStage.ANONYMIZED, [PipelineStage.INGESTED], False, compute_b),
    ]

    executor = DAGExecutor(conn, dag)

    # First execution
    results1 = executor.execute_to_stage(PipelineStage.ANONYMIZED)
    assert call_count["a"] == 1
    assert call_count["b"] == 1
    assert not results1[0].was_cached
    assert not results1[1].was_cached

    # Second execution - should use cache
    executor2 = DAGExecutor(conn, dag)
    results2 = executor2.execute_to_stage(PipelineStage.ANONYMIZED)
    assert call_count["a"] == 1  # Not called again
    assert call_count["b"] == 1  # Not called again
    assert results2[0].was_cached
    assert results2[1].was_cached


def test_force_refresh():
    """Test force_refresh recomputes even cached stages."""
    conn = ibis.duckdb.connect()

    call_count = {"a": 0}

    def compute_a(conn, upstream):
        call_count["a"] += 1
        return ibis.memtable({"id": [call_count["a"]], "value": ["a"]})

    dag = [StageDependency(PipelineStage.INGESTED, [], False, compute_a)]

    # First execution
    executor = DAGExecutor(conn, dag)
    results1 = executor.execute_to_stage(PipelineStage.INGESTED)
    assert call_count["a"] == 1
    assert not results1[0].was_cached

    # Second execution without force_refresh - uses cache
    executor2 = DAGExecutor(conn, dag)
    results2 = executor2.execute_to_stage(PipelineStage.INGESTED, force_refresh=False)
    assert call_count["a"] == 1
    assert results2[0].was_cached

    # Third execution with force_refresh - recomputes
    executor3 = DAGExecutor(conn, dag)
    results3 = executor3.execute_to_stage(PipelineStage.INGESTED, force_refresh=True)
    assert call_count["a"] == 2  # noqa: PLR2004
    assert not results3[0].was_cached


def test_materialized_vs_view():
    """Test that materialized stages create tables, views create views."""
    conn = ibis.duckdb.connect()

    def compute_a(conn, upstream):
        return ibis.memtable({"id": [1], "value": ["a"]})

    def compute_b(conn, upstream):
        return upstream[PipelineStage.INGESTED].mutate(stage=ibis.literal("b"))

    dag = [
        StageDependency(PipelineStage.INGESTED, [], materialized=False, compute_fn=compute_a),
        StageDependency(
            PipelineStage.ANONYMIZED,
            [PipelineStage.INGESTED],
            materialized=True,
            compute_fn=compute_b,
        ),
    ]

    executor = DAGExecutor(conn, dag)
    executor.execute_to_stage(PipelineStage.ANONYMIZED)

    # Both should exist
    assert PipelineStage.INGESTED.value in conn.list_tables()
    assert PipelineStage.ANONYMIZED.value in conn.list_tables()

    # Note: DuckDB doesn't distinguish views from tables in list_tables()
    # but the materialization flag affects caching behavior


def test_execution_result_fields():
    """Test that execution results contain expected fields."""
    conn = ibis.duckdb.connect()

    def compute_a(conn, upstream):
        return ibis.memtable({"id": [1, 2, 3], "value": ["a", "b", "c"]})

    dag = [StageDependency(PipelineStage.INGESTED, [], False, compute_a)]

    executor = DAGExecutor(conn, dag)
    results = executor.execute_to_stage(PipelineStage.INGESTED)

    assert len(results) == 1
    result = results[0]

    assert result.stage == PipelineStage.INGESTED
    assert result.duration_seconds > 0
    assert result.row_count == 3  # noqa: PLR2004
    assert result.was_cached is False
    assert result.error is None


def test_error_handling():
    """Test that stage errors are captured in results."""
    conn = ibis.duckdb.connect()

    def compute_a(conn, upstream):
        raise ValueError("Simulated error")

    dag = [StageDependency(PipelineStage.INGESTED, [], False, compute_a)]

    executor = DAGExecutor(conn, dag)
    results = executor.execute_to_stage(PipelineStage.INGESTED)

    assert len(results) == 1
    result = results[0]

    assert result.error is not None
    assert isinstance(result.error, ValueError)
    assert "Simulated error" in str(result.error)


def test_missing_dependency():
    """Test error when dependency is missing."""
    conn = ibis.duckdb.connect()

    def compute_a(conn, upstream):
        return ibis.memtable({"id": [1], "value": ["a"]})

    def compute_b(conn, upstream):
        # Try to access non-existent dependency (not in conn yet)
        return upstream[PipelineStage.INGESTED].mutate(stage=ibis.literal("b"))

    # Define B that depends on A, but A is not in the DAG
    # This tests the case where compute_b won't be able to find the dependency
    dag = [
        StageDependency(
            PipelineStage.ANONYMIZED,
            [PipelineStage.INGESTED],
            False,
            compute_b,
        ),
    ]

    executor = DAGExecutor(conn, dag)

    # This should raise an error during execution because INGESTED dependency not found
    results = executor.execute_to_stage(PipelineStage.ANONYMIZED)

    # Should fail with error
    assert len(results) == 1
    assert results[0].error is not None
    assert "not found" in str(results[0].error).lower()


def test_build_pipeline_dag_helper():
    """Test build_pipeline_dag helper function."""
    def compute_ingested(conn, upstream):
        return ibis.memtable({"id": [1], "msg": ["ingested"]})

    def compute_anonymized(conn, upstream):
        return upstream[PipelineStage.INGESTED].mutate(msg="anonymized")

    dag = build_pipeline_dag({
        PipelineStage.INGESTED: compute_ingested,
        PipelineStage.ANONYMIZED: compute_anonymized,
    })

    # Should have all 4 standard stages
    assert len(dag) == 4  # noqa: PLR2004

    # Verify stages exist
    stage_names = {sd.stage for sd in dag}
    assert PipelineStage.INGESTED in stage_names
    assert PipelineStage.ANONYMIZED in stage_names
    assert PipelineStage.ENRICHED in stage_names
    assert PipelineStage.KNOWLEDGE in stage_names

    # Verify ENRICHED is materialized
    enriched_def = next(sd for sd in dag if sd.stage == PipelineStage.ENRICHED)
    assert enriched_def.materialized is True


def test_row_count_tracking():
    """Test that row counts are correctly tracked."""
    conn = ibis.duckdb.connect()

    def compute_a(conn, upstream):
        return ibis.memtable({"id": list(range(100)), "value": ["x"] * 100})

    dag = [StageDependency(PipelineStage.INGESTED, [], False, compute_a)]

    executor = DAGExecutor(conn, dag)
    results = executor.execute_to_stage(PipelineStage.INGESTED)

    assert results[0].row_count == 100  # noqa: PLR2004


def test_multiple_executions_different_executors():
    """Test that multiple executor instances work correctly."""
    conn = ibis.duckdb.connect()

    def compute_a(conn, upstream):
        return ibis.memtable({"id": [1], "value": ["a"]})

    dag = [StageDependency(PipelineStage.INGESTED, [], False, compute_a)]

    # First executor
    executor1 = DAGExecutor(conn, dag)
    results1 = executor1.execute_to_stage(PipelineStage.INGESTED)
    assert not results1[0].was_cached

    # Second executor (different instance)
    executor2 = DAGExecutor(conn, dag)
    results2 = executor2.execute_to_stage(PipelineStage.INGESTED)
    assert results2[0].was_cached  # Uses cache from first execution


def test_print_summary():
    """Test print_summary doesn't crash."""
    conn = ibis.duckdb.connect()

    def compute_a(conn, upstream):
        return ibis.memtable({"id": [1, 2, 3], "value": ["a", "b", "c"]})

    dag = [StageDependency(PipelineStage.INGESTED, [], False, compute_a)]

    executor = DAGExecutor(conn, dag)
    executor.execute_to_stage(PipelineStage.INGESTED)

    # Should not crash
    executor.print_summary()
