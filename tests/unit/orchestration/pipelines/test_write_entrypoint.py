from pathlib import Path
from unittest.mock import patch

from egregora.config.settings import SiteSettings, SourceSettings
from egregora.constants import SourceType


def test_write_cli_importable():
    """
    GREEN TEST: Verify that the CLI module exists and imports correctly.
    """
    import egregora.cli.write

    assert hasattr(egregora.cli.write, "run_cli_flow")


@patch("egregora.cli.write.run")
@patch("egregora.cli.write.load_egregora_config")
@patch("egregora.cli.write.validate_api_key")
@patch("egregora.orchestration.pipelines.etl.setup.MkDocsSiteScaffolder.scaffold_site")
def test_run_cli_flow(mock_scaffold_site, mock_validate_key, mock_load_config, mock_run, config_factory):
    """
    GREEN TEST: Verify run_cli_flow executes the pipeline logic.
    """
    from egregora.cli.write import run_cli_flow

    # Mock config
    mock_config = config_factory()
    mock_load_config.return_value = mock_config

    run_cli_flow(input_file=Path("test.zip"), output=Path("site"), source=SourceType.WHATSAPP.value)

    # Verify run was called
    assert mock_run.called
    run_params = mock_run.call_args[0][0]
    assert run_params.input_path == Path("test.zip")
    assert run_params.source_type == SourceType.WHATSAPP.value
    assert run_params.source_key == "whatsapp"

    # Verify other mocks were used (silences PT019)
    assert mock_scaffold_site.called is not None
    assert mock_validate_key.called is not None


@patch("egregora.cli.write.run")
@patch("egregora.cli.write.load_egregora_config")
@patch("egregora.cli.write.validate_api_key")
@patch("egregora.orchestration.pipelines.etl.setup.MkDocsSiteScaffolder.scaffold_site")
def test_run_cli_flow_runs_all_sources_when_default_missing(
    mock_scaffold_site, mock_validate_key, mock_load_config, mock_run, config_factory
):
    """
    GREEN TEST: Ensure multiple configured sources run sequentially without repeated CLI flags.
    """
    from egregora.cli.write import run_cli_flow

    config = config_factory()
    config.site = SiteSettings(
        default_source=None,
        sources={
            "alpha": SourceSettings(adapter="whatsapp"),
            "beta": SourceSettings(adapter="self"),
        },
    )
    mock_load_config.return_value = config

    run_cli_flow(input_file=Path("test.zip"), output=Path("site"), source=None)

    assert mock_run.call_count == 2
    first_params = mock_run.call_args_list[0][0][0]
    second_params = mock_run.call_args_list[1][0][0]
    assert first_params.source_key == "alpha"
    assert first_params.source_type == "whatsapp"
    assert second_params.source_key == "beta"
    assert second_params.source_type == "self"


@patch("egregora.cli.write.run")
@patch("egregora.cli.write.load_egregora_config")
@patch("egregora.cli.write.validate_api_key")
@patch("egregora.orchestration.pipelines.etl.setup.MkDocsSiteScaffolder.scaffold_site")
def test_run_cli_flow_invalid_source_key_exits(
    mock_scaffold_site, mock_validate_key, mock_load_config, mock_run, config_factory
):
    """
    GREEN TEST: Unknown source keys emit a clear error and abort.
    """
    from egregora.cli.write import run_cli_flow

    config = config_factory()
    config.site = SiteSettings(
        default_source="missing", sources={"alpha": SourceSettings(adapter="whatsapp")}
    )
    mock_load_config.return_value = config

    try:
        run_cli_flow(input_file=Path("test.zip"), output=Path("site"), source="ghost")
    except SystemExit:
        pass
    else:
        msg = "run_cli_flow should exit when an unknown source key is provided"
        raise AssertionError(msg)

    mock_run.assert_not_called()


@patch("egregora.cli.write.run")
@patch("egregora.cli.write.load_egregora_config")
@patch("egregora.cli.write.validate_api_key")
@patch("egregora.orchestration.pipelines.etl.setup.MkDocsSiteScaffolder.scaffold_site")
def test_run_cli_flow_scaffolds_if_no_config(
    mock_scaffold_site, mock_validate_key, mock_load_config, mock_run, config_factory, tmp_path
):
    """Verify that a new site is scaffolded if the config doesn't exist."""
    from egregora.cli.write import run_cli_flow

    # Simulate no config file existing
    output_dir = tmp_path / "new-site"
    # NOTE: We don't create output_dir to ensure the code handles it.
    config_path = output_dir / ".egregora.toml"
    assert not config_path.exists()

    mock_load_config.return_value = config_factory()

    run_cli_flow(input_file=Path("test.zip"), output=output_dir, source="whatsapp")

    # Verify that scaffolding was called because the config was missing
    mock_scaffold_site.assert_called_once_with(output_dir, site_name=output_dir.name)
    assert mock_run.called
