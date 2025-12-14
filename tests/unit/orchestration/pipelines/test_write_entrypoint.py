from pathlib import Path
from unittest.mock import MagicMock, patch

from egregora.constants import SourceType


def test_write_pipeline_importable():
    """
    GREEN TEST: Verify that the module now exists and can be imported.
    """
    import egregora.orchestration.pipelines.write

    assert hasattr(egregora.orchestration.pipelines.write, "run_cli_flow")


@patch("egregora.orchestration.pipelines.write.run")
@patch("egregora.orchestration.pipelines.write.load_egregora_config")
@patch("egregora.orchestration.pipelines.write._validate_api_key")
@patch("egregora.orchestration.pipelines.write.ensure_mkdocs_project")
def test_run_cli_flow(mock_ensure_mkdocs, mock_validate_key, mock_load_config, mock_run):
    """
    GREEN TEST: Verify run_cli_flow executes the pipeline logic.
    """
    from egregora.orchestration.pipelines.write import run_cli_flow

    # Mock config
    mock_config = MagicMock()
    mock_load_config.return_value = mock_config
    # Mock model_copy to return self or a new mock
    mock_config.model_copy.return_value = mock_config
    mock_config.pipeline.model_copy.return_value = mock_config.pipeline

    run_cli_flow(input_file=Path("test.zip"), output=Path("site"), source=SourceType.WHATSAPP)

    # Verify run was called
    assert mock_run.called
    run_params = mock_run.call_args[0][0]
    assert run_params.input_path == Path("test.zip")
    assert run_params.source_type == SourceType.WHATSAPP.value
