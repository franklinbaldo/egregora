"""Tests for the write pipeline orchestration logic.

These tests verify that the WritePipeline correctly orchestrates the CLI logic,
including configuration setup and validation, before delegating to the core pipeline.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer import Exit

from egregora.cli.main import WriteCommandOptions
from egregora.constants import SourceType, WindowUnit
from egregora.orchestration.pipelines.write import WritePipeline


class TestWritePipelineOrchestration:
    """Tests for the WritePipeline orchestration layer."""

    @pytest.fixture
    def mock_write_pipeline_run(self):
        """Mock the underlying write_pipeline.run function."""
        with patch("egregora.orchestration.pipelines.write.write_pipeline.run") as mock_run:
            yield mock_run

    @pytest.fixture
    def mock_ensure_mkdocs(self):
        """Mock the _ensure_mkdocs_scaffold function (or its equivalent)."""
        with patch("egregora.orchestration.pipelines.write._ensure_mkdocs_scaffold") as mock:
            yield mock

    @pytest.fixture
    def mock_validate_api_key(self):
        """Mock the _validate_api_key function."""
        with patch("egregora.orchestration.pipelines.write._validate_api_key") as mock:
            yield mock

    @pytest.fixture
    def mock_load_config(self):
        """Mock load_egregora_config."""
        with patch("egregora.orchestration.pipelines.write.load_egregora_config") as mock:
            mock.return_value = MagicMock()
            mock.return_value.model_copy.return_value = MagicMock()
            yield mock

    def test_run_validates_api_key(
        self,
        mock_write_pipeline_run,
        mock_ensure_mkdocs,
        mock_validate_api_key,
        mock_load_config,
        tmp_path,
    ):
        """Test that run() validates the API key."""
        pipeline = WritePipeline()
        options = WriteCommandOptions(
            input_file=Path("input.zip"),
            source=SourceType.WHATSAPP,
            output=tmp_path,
            step_size=100,
            step_unit=WindowUnit.MESSAGES,
            overlap=0.0,
            enable_enrichment=True,
            from_date=None,
            to_date=None,
            timezone=None,
            model=None,
            max_prompt_tokens=400000,
            use_full_context_window=False,
            max_windows=None,
            resume=True,
            refresh=None,
            force=False,
            debug=False,
        )

        pipeline.run(options)

        mock_validate_api_key.assert_called_once()
        mock_ensure_mkdocs.assert_called_once()
        mock_write_pipeline_run.assert_called_once()

    def test_run_validates_dates(self, mock_write_pipeline_run, mock_load_config, tmp_path):
        """Test that run() validates date formats."""
        pipeline = WritePipeline()
        options = WriteCommandOptions(
            input_file=Path("input.zip"),
            source=SourceType.WHATSAPP,
            output=tmp_path,
            step_size=100,
            step_unit=WindowUnit.MESSAGES,
            overlap=0.0,
            enable_enrichment=True,
            from_date="invalid-date",
            to_date=None,
            timezone=None,
            model=None,
            max_prompt_tokens=400000,
            use_full_context_window=False,
            max_windows=None,
            resume=True,
            refresh=None,
            force=False,
            debug=False,
        )

        # We expect a Typer Exit exception due to validation failure
        with pytest.raises(Exit):
            pipeline.run(options)

        mock_write_pipeline_run.assert_not_called()

    def test_run_validates_timezone(self, mock_write_pipeline_run, mock_load_config, tmp_path):
        """Test that run() validates timezone."""
        pipeline = WritePipeline()
        options = WriteCommandOptions(
            input_file=Path("input.zip"),
            source=SourceType.WHATSAPP,
            output=tmp_path,
            step_size=100,
            step_unit=WindowUnit.MESSAGES,
            overlap=0.0,
            enable_enrichment=True,
            from_date=None,
            to_date=None,
            timezone="Invalid/Timezone",
            model=None,
            max_prompt_tokens=400000,
            use_full_context_window=False,
            max_windows=None,
            resume=True,
            refresh=None,
            force=False,
            debug=False,
        )

        with pytest.raises(Exit):
            pipeline.run(options)

        mock_write_pipeline_run.assert_not_called()

    def test_run_resolves_config(
        self,
        mock_write_pipeline_run,
        mock_ensure_mkdocs,
        mock_validate_api_key,
        mock_load_config,
        tmp_path,
    ):
        """Test that run() prepares configuration correctly."""
        pipeline = WritePipeline()
        options = WriteCommandOptions(
            input_file=Path("input.zip"),
            source=SourceType.WHATSAPP,
            output=tmp_path,
            step_size=50,  # Custom
            step_unit=WindowUnit.HOURS,  # Custom
            overlap=0.1,  # Custom
            enable_enrichment=False,  # Custom
            from_date=None,
            to_date=None,
            timezone=None,
            model="custom-model",  # Custom
            max_prompt_tokens=100000,  # Custom
            use_full_context_window=True,  # Custom
            max_windows=5,  # Custom
            resume=False,  # Custom
            refresh="all",
            force=True,
            debug=True,
        )

        pipeline.run(options)

        mock_load_config.assert_called_once_with(tmp_path)
        # Verify that config update logic was called (checking model_copy calls)
        config_mock = mock_load_config.return_value
        config_mock.model_copy.assert_called()

        # Check call arguments to write_pipeline.run
        args, _ = mock_write_pipeline_run.call_args
        run_params = args[0]
        assert run_params.output_dir == tmp_path.expanduser().resolve()
        assert run_params.input_path == Path("input.zip")
        # Refresh logic: force=True means refresh="all"
        assert run_params.refresh == "all"
