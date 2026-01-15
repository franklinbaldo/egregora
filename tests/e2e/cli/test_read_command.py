"""E2E tests for the 'egregora read' CLI command."""

from pathlib import Path

import pytest
import tomli_w
from typer.testing import CliRunner

from egregora.cli.main import app

# Create a CLI runner for testing
runner = CliRunner()


@pytest.fixture
def mock_site_root(tmp_path: Path, config_factory) -> Path:
    """Creates a mock site root with the necessary config and directories."""
    site_root = tmp_path / "test_site"
    site_root.mkdir()

    def clean_none_values(data):
        """Recursively remove keys with None values from dictionaries and lists."""
        if isinstance(data, dict):
            # Clean dictionary: recurse on values and filter keys where the new value is None
            cleaned_dict = {}
            for k, v in data.items():
                cleaned_v = clean_none_values(v)
                if cleaned_v is not None:
                    cleaned_dict[k] = cleaned_v
            return cleaned_dict
        if isinstance(data, list):
            # Clean list: recurse on items and filter out any resulting Nones
            return [clean_none_values(item) for item in data if item is not None]
        # Return the item as is if it's not a dict or list
        return data

    # Create the .egregora directory, which the CLI checks for
    (site_root / ".egregora").mkdir()

    # The app expects .egregora.toml in the site root
    config = config_factory()
    config.reader.enabled = True  # Enable the reader to reach the target code path
    config_path = site_root / ".egregora.toml"

    # Clean the config dict before dumping to TOML
    config_dict = config.model_dump(mode="json")
    cleaned_config = clean_none_values(config_dict)

    with config_path.open("wb") as f:
        # Use tomli_w to write the cleaned dictionary
        tomli_w.dump(cleaned_config, f)

    # Create a posts directory
    (site_root / "docs" / "posts").mkdir(parents=True)

    return site_root


