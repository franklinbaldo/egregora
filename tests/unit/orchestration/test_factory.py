"""Unit tests for the pipeline factory."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from egregora.config.settings import DatabaseSettings, EgregoraConfig
from egregora.orchestration.context import PipelineContext, PipelineRunParams
from egregora.orchestration.factory import PipelineFactory


@pytest.fixture
def mock_run_params(tmp_path):
    """Provides mock PipelineRunParams for testing."""
    config = EgregoraConfig(
        database=DatabaseSettings(
            pipeline_db=f"duckdb:///{tmp_path}/test_pipeline.duckdb",
            runs_db=f"duckdb:///{tmp_path}/test_runs.duckdb",
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
    with patch.object(
        PipelineFactory, "resolve_site_paths_or_raise", return_value=MagicMock()
    ) as mock_resolve_paths, patch.object(
        PipelineFactory,
        "create_database_backends",
        return_value=("mock_db_uri", MagicMock(), MagicMock()),
    ) as mock_create_db, patch(
        "egregora.orchestration.factory.initialize_database"
    ) as mock_init_db, patch.object(
        PipelineFactory, "create_gemini_client"
    ) as mock_create_client, patch(
        "egregora.orchestration.factory.PipelineCache"
    ) as mock_cache, patch(
        "egregora.orchestration.factory.DuckDBStorageManager"
    ) as mock_storage, patch(
        "egregora.orchestration.factory.create_default_output_registry"
    ) as mock_create_registry, patch.object(
        PipelineFactory, "create_output_adapter"
    ) as mock_create_adapter, patch(
        "egregora.orchestration.factory.AnnotationStore"
    ) as mock_annotation_store:
        # Setup mock return value for the adapter
        mock_adapter = MagicMock()
        mock_create_adapter.return_value = mock_adapter

        # Call the method under test
        context, _, _ = PipelineFactory.create_context(mock_run_params)

        # Assertions
        assert isinstance(context, PipelineContext)
        mock_resolve_paths.assert_called_once()
        mock_create_db.assert_called_once()
        mock_init_db.assert_called_once()
        mock_create_client.assert_called_once()
        mock_cache.assert_called_once()
        mock_storage.assert_called_once()
        mock_create_registry.assert_called_once()
        mock_create_adapter.assert_called_once()
        mock_annotation_store.assert_called_once()

        assert context.config is not None
        assert context.state is not None
        assert context.state.run_id == "test-run"
        # Assert that the output_format is correctly assigned
        assert context.state.output_format is mock_adapter
