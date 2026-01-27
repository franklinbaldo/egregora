"""Unit tests for the pipeline factory."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from egregora.config.settings import DatabaseSettings, EgregoraConfig
from egregora.orchestration.context import PipelineContext, PipelineRunParams
from egregora.orchestration.pipelines.etl.setup import _create_pipeline_context


@pytest.fixture
def mock_run_params(tmp_path):
    """Provides mock PipelineRunParams for testing."""
    config = EgregoraConfig(
        database=DatabaseSettings(
            pipeline_db=f"duckdb:///{tmp_path}/test_pipeline.duckdb",
        )
    )
    return PipelineRunParams(
        run_id="test-run",
        start_time=datetime.now(),
        source_type="test",
        config=config,
        output_dir=tmp_path,
        input_path=tmp_path / "input.txt",
    )


def test_create_context(mock_run_params):
    """Tests that create_context initializes PipelineContext and its resources correctly."""
    with (
        patch("egregora.orchestration.pipelines.etl.setup._resolve_site_paths_or_raise") as mock_resolve_paths,
        patch("egregora.orchestration.pipelines.etl.setup._create_database_backend", return_value=("mock_db_uri", MagicMock())) as mock_create_db,
        patch("egregora.orchestration.pipelines.etl.setup.initialize_database") as mock_init_db,
        patch("egregora.orchestration.pipelines.etl.setup._create_gemini_client") as mock_create_client,
        patch("egregora.orchestration.pipelines.etl.setup.PipelineCache") as mock_cache,
        patch("egregora.orchestration.pipelines.etl.setup.DuckDBStorageManager") as mock_storage,
        patch("egregora.orchestration.pipelines.etl.setup.create_default_output_registry") as mock_create_registry,
        patch("egregora.orchestration.pipelines.etl.setup.AnnotationStore") as mock_annotation_store,
    ):
        mock_resolve_paths.return_value = MagicMock()

        # Call the method under test
        context, _ = _create_pipeline_context(mock_run_params)

        # Assertions
        assert isinstance(context, PipelineContext)
        mock_resolve_paths.assert_called_once()
        mock_create_db.assert_called_once()
        mock_init_db.assert_called_once()
        mock_create_client.assert_called_once()
        mock_cache.assert_called_once()
        mock_storage.from_ibis_backend.assert_called_once()
        mock_create_registry.assert_called_once()
        mock_annotation_store.assert_called_once()

        assert context.config is not None
        assert context.state is not None
        assert context.state.run_id == "test-run"
