"""DAG-based pipeline orchestration.

Provides declarative dependency graph for pipeline stages with:
- Topological sorting for correct execution order
- Caching/materialization support
- Incremental computation (only recompute stale stages)
- Observability (timing, row counts, stage status)
"""

import logging
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

import ibis
from ibis.expr.types import Table

from ..core.database_schema import PipelineStage, materialize_stage, stage_exists

logger = logging.getLogger(__name__)


@dataclass
class StageDependency:
    """
    Defines a pipeline stage with its dependencies.

    Attributes:
        stage: Pipeline stage enum value
        depends_on: List of stages that must complete before this stage
        materialized: Whether to cache as table (True) or compute as view (False)
        compute_fn: Function that computes this stage given upstream stages
    """

    stage: PipelineStage
    depends_on: list[PipelineStage]
    materialized: bool = False
    compute_fn: Callable[[ibis.BaseBackend, dict[PipelineStage, Table]], Table] | None = None


@dataclass
class StageExecutionResult:
    """Result of executing a pipeline stage."""

    stage: PipelineStage
    duration_seconds: float
    row_count: int
    was_cached: bool
    error: Exception | None = None


class DAGExecutor:
    """
    Executes pipeline stages in dependency order with caching.

    Example:
        >>> conn = ibis.duckdb.connect("pipeline.duckdb")
        >>> executor = DAGExecutor(conn, PIPELINE_DAG)
        >>> executor.execute_to_stage(PipelineStage.ENRICHED, force_refresh=False)
    """

    def __init__(self, conn: ibis.BaseBackend, dag: list[StageDependency]):
        """
        Initialize DAG executor.

        Args:
            conn: Ibis connection to database
            dag: List of stage dependencies defining the pipeline
        """
        self.conn = conn
        self.dag = dag
        self.execution_results: list[StageExecutionResult] = []

    def execute_to_stage(
        self,
        target: PipelineStage,
        *,
        force_refresh: bool = False,
    ) -> list[StageExecutionResult]:
        """
        Execute pipeline DAG up to target stage.

        Args:
            target: Final stage to compute
            force_refresh: If True, recompute all stages even if cached

        Returns:
            List of execution results for each stage that ran

        Example:
            >>> results = executor.execute_to_stage(PipelineStage.ENRICHED)
            >>> for result in results:
            ...     print(f"{result.stage.value}: {result.duration_seconds:.2f}s")
        """
        # Get stages in execution order
        stages_to_run = self._get_execution_order(target)

        logger.info(f"Executing pipeline to {target.value} ({len(stages_to_run)} stages)")

        # Execute each stage
        results = []
        for stage_def in stages_to_run:
            result = self._execute_stage(stage_def, force_refresh=force_refresh)
            results.append(result)
            self.execution_results.append(result)

            if result.error:
                logger.error(f"Stage {stage_def.stage.value} failed: {result.error}")
                break

        return results

    def _get_execution_order(self, target: PipelineStage) -> list[StageDependency]:
        """
        Get stages in topological order up to target.

        Returns:
            List of StageDependency in execution order
        """
        # Build dependency graph
        stage_to_def = {sd.stage: sd for sd in self.dag}

        # Find all stages needed to reach target
        needed_stages = set()
        self._collect_dependencies(target, stage_to_def, needed_stages)

        # Topological sort
        sorted_stages = self._topological_sort(needed_stages, stage_to_def)

        # Only return stages that have definitions
        return [stage_to_def[stage] for stage in sorted_stages if stage in stage_to_def]

    def _collect_dependencies(
        self,
        stage: PipelineStage,
        stage_to_def: dict[PipelineStage, StageDependency],
        collected: set[PipelineStage],
    ) -> None:
        """Recursively collect all dependencies for a stage."""
        if stage in collected:
            return

        stage_def = stage_to_def.get(stage)
        if not stage_def:
            # Stage not defined in DAG - still collect it so we can check later
            collected.add(stage)
            return

        collected.add(stage)

        for dep in stage_def.depends_on:
            self._collect_dependencies(dep, stage_to_def, collected)

    def _topological_sort(
        self,
        stages: set[PipelineStage],
        stage_to_def: dict[PipelineStage, StageDependency],
    ) -> list[PipelineStage]:
        """
        Sort stages in topological order (dependencies first).

        Uses Kahn's algorithm for topological sorting.
        """
        # Build adjacency list and in-degree count
        in_degree = defaultdict(int)
        adjacency = defaultdict(list)

        for stage in stages:
            stage_def = stage_to_def.get(stage)
            if not stage_def:
                continue

            for dep in stage_def.depends_on:
                if dep in stages:
                    adjacency[dep].append(stage)
                    in_degree[stage] += 1

        # Initialize with stages that have no dependencies
        queue = [s for s in stages if in_degree[s] == 0]
        result = []

        while queue:
            # Process node with no remaining dependencies
            current = queue.pop(0)
            result.append(current)

            # Reduce in-degree for dependent nodes
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(result) != len(stages):
            raise ValueError("DAG contains a cycle - cannot execute")

        return result

    def _execute_stage(
        self,
        stage_def: StageDependency,
        *,
        force_refresh: bool = False,
    ) -> StageExecutionResult:
        """Execute a single pipeline stage."""
        stage = stage_def.stage
        start_time = time.time()

        try:
            # Check if stage already exists and is fresh
            if not force_refresh and stage_exists(self.conn, stage):
                table = self.conn.table(stage.value)
                row_count = int(table.count().execute())
                duration = time.time() - start_time

                logger.info(
                    f"[{stage.value}] Using cached ({row_count} rows, {duration:.2f}s to verify)"
                )

                return StageExecutionResult(
                    stage=stage,
                    duration_seconds=duration,
                    row_count=row_count,
                    was_cached=True,
                )

            # Compute stage
            if not stage_def.compute_fn:
                raise ValueError(f"Stage {stage.value} has no compute function")

            logger.info(f"[{stage.value}] Computing...")

            # Get upstream stage results
            upstream_tables = {}
            for dep_stage in stage_def.depends_on:
                if stage_exists(self.conn, dep_stage):
                    upstream_tables[dep_stage] = self.conn.table(dep_stage.value)
                else:
                    raise ValueError(f"Dependency {dep_stage.value} not found for {stage.value}")

            # Compute stage result
            result_table = stage_def.compute_fn(self.conn, upstream_tables)

            # Materialize or create view
            if stage_def.materialized:
                materialize_stage(self.conn, stage, result_table, overwrite=True)
            else:
                self.conn.create_view(stage.value, result_table, overwrite=True)

            # Get row count
            final_table = self.conn.table(stage.value)
            row_count = int(final_table.count().execute())

            duration = time.time() - start_time

            cache_status = "materialized" if stage_def.materialized else "view"
            logger.info(f"[{stage.value}] Complete ({row_count} rows, {duration:.2f}s, {cache_status})")

            return StageExecutionResult(
                stage=stage,
                duration_seconds=duration,
                row_count=row_count,
                was_cached=False,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[{stage.value}] Failed after {duration:.2f}s: {e}")

            return StageExecutionResult(
                stage=stage,
                duration_seconds=duration,
                row_count=0,
                was_cached=False,
                error=e,
            )

    def print_summary(self) -> None:
        """Print execution summary with timing and row counts."""
        if not self.execution_results:
            logger.info("No stages executed")
            return

        total_time = sum(r.duration_seconds for r in self.execution_results)
        total_rows = sum(r.row_count for r in self.execution_results)

        print("\n" + "=" * 70)
        print("Pipeline Execution Summary")
        print("=" * 70)

        for i, result in enumerate(self.execution_results, 1):
            status = "✓" if not result.error else "✗"
            cache_str = " [cached]" if result.was_cached else ""
            error_str = f" - {result.error}" if result.error else ""

            print(
                f"[{i}/{len(self.execution_results)}] {status} {result.stage.value}: "
                f"{result.row_count:,} rows, {result.duration_seconds:.2f}s{cache_str}{error_str}"
            )

        print("=" * 70)
        print(f"Total: {total_rows:,} rows, {total_time:.2f}s")
        print("=" * 70 + "\n")


# ============================================================================
# Helper Functions
# ============================================================================


def build_pipeline_dag(
    stage_compute_fns: dict[PipelineStage, Callable[[ibis.BaseBackend, dict[PipelineStage, Table]], Table]]
) -> list[StageDependency]:
    """
    Build a standard pipeline DAG with provided compute functions.

    Args:
        stage_compute_fns: Mapping of stages to their compute functions

    Returns:
        List of StageDependency defining the full pipeline

    Example:
        >>> def compute_anonymized(conn, upstream):
        ...     ingested = upstream[PipelineStage.INGESTED]
        ...     return ingested.mutate(author=anonymize(ingested.author))
        >>>
        >>> dag = build_pipeline_dag({
        ...     PipelineStage.INGESTED: compute_ingested,
        ...     PipelineStage.ANONYMIZED: compute_anonymized,
        ... })
    """
    dag = [
        StageDependency(
            stage=PipelineStage.INGESTED,
            depends_on=[],
            materialized=False,
            compute_fn=stage_compute_fns.get(PipelineStage.INGESTED),
        ),
        StageDependency(
            stage=PipelineStage.ANONYMIZED,
            depends_on=[PipelineStage.INGESTED],
            materialized=False,
            compute_fn=stage_compute_fns.get(PipelineStage.ANONYMIZED),
        ),
        StageDependency(
            stage=PipelineStage.ENRICHED,
            depends_on=[PipelineStage.ANONYMIZED],
            materialized=True,  # Expensive - cache results
            compute_fn=stage_compute_fns.get(PipelineStage.ENRICHED),
        ),
        StageDependency(
            stage=PipelineStage.KNOWLEDGE,
            depends_on=[PipelineStage.ENRICHED],
            materialized=False,
            compute_fn=stage_compute_fns.get(PipelineStage.KNOWLEDGE),
        ),
    ]

    return dag
