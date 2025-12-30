"""E2E tests for the 'egregora show' and 'egregora top' CLI commands."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import tomli_w
from typer.testing import CliRunner

from egregora.cli.main import app
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.elo_store import EloStore
from egregora.database.utils import get_simple_storage

# Create a CLI runner for testing
runner = CliRunner()


def clean_none_values(data):
    """Recursively remove keys with None values from dictionaries and lists."""
    if isinstance(data, dict):
        cleaned_dict = {}
        for k, v in data.items():
            cleaned_v = clean_none_values(v)
            if cleaned_v is not None:
                cleaned_dict[k] = cleaned_v
        return cleaned_dict
    if isinstance(data, list):
        return [clean_none_values(item) for item in data if item is not None]
    return data


@pytest.fixture
def mock_site_root_with_db(tmp_path: Path, config_factory) -> Path:
    """Creates a mock site root with a pre-initialized database."""
    site_root = tmp_path / "test_site"
    site_root.mkdir()

    # Create the .egregora directory, which the CLI checks for
    (site_root / ".egregora").mkdir(exist_ok=True)

    # The app expects .egregora.toml in the site root
    config = config_factory()
    config.reader.database_path = ".egregora/reader.duckdb"
    config_path = site_root / ".egregora.toml"

    config_dict = config.model_dump(mode="json")
    cleaned_config = clean_none_values(config_dict)

    with config_path.open("wb") as f:
        tomli_w.dump(cleaned_config, f)

    # Initialize the database and tables
    db_path = site_root / config.reader.database_path
    storage = DuckDBStorageManager(db_path)
    elo_store = EloStore(storage)
    elo_store._ensure_tables()

    return site_root


@pytest.fixture
def mock_site_root_without_db(tmp_path: Path, config_factory) -> Path:
    """Creates a mock site root without a database."""
    site_root = tmp_path / "test_site"
    site_root.mkdir()

    (site_root / ".egregora").mkdir(exist_ok=True)

    config = config_factory()
    config.reader.database_path = ".egregora/reader.duckdb"
    config_path = site_root / ".egregora.toml"

    config_dict = config.model_dump(mode="json")
    cleaned_config = clean_none_values(config_dict)

    with config_path.open("wb") as f:
        tomli_w.dump(cleaned_config, f)

    return site_root


def test_top_command(mock_site_root_with_db: Path):
    """Test the 'top' command with mock data."""
    db_path = mock_site_root_with_db / ".egregora/reader.duckdb"
    storage = get_simple_storage(db_path)
    elo_store = EloStore(storage)
    datetime.now(UTC)

    # Insert mock data using the EloStore API
    elo_store.update_ratings(
        EloStore.UpdateParams(
            post_a_slug="post-c",
            post_b_slug="post-b",
            rating_a_new=1700.0,
            rating_b_new=1600.0,
            winner="a",
            comparison_id=str(uuid.uuid4()),
        )
    )
    elo_store.update_ratings(
        EloStore.UpdateParams(
            post_a_slug="post-b",
            post_b_slug="post-a",
            rating_a_new=1600.0,
            rating_b_new=1500.0,
            winner="a",
            comparison_id=str(uuid.uuid4()),
        )
    )

    result = runner.invoke(app, ["top", str(mock_site_root_with_db)])

    assert result.exit_code == 0, result.stdout
    assert "🏆 Top 10 Posts" in result.stdout
    assert "post-c" in result.stdout
    assert "post-b" in result.stdout
    assert "post-a" in result.stdout
    # Check the order
    assert result.stdout.find("post-c") < result.stdout.find("post-b") < result.stdout.find("post-a")


def test_show_reader_history_command(mock_site_root_with_db: Path):
    """Test the 'show reader-history' command with mock data."""
    db_path = mock_site_root_with_db / ".egregora/reader.duckdb"
    storage = get_simple_storage(db_path)
    elo_store = EloStore(storage)
    datetime.now(UTC)

    # Insert mock data using the EloStore API
    elo_store.update_ratings(
        EloStore.UpdateParams(
            post_a_slug="post-a",
            post_b_slug="post-b",
            rating_a_new=1510.0,
            rating_b_new=1590.0,
            winner="a",
            comparison_id=str(uuid.uuid4()),
        )
    )
    elo_store.update_ratings(
        EloStore.UpdateParams(
            post_a_slug="post-c",
            post_b_slug="post-a",
            rating_a_new=1690.0,
            rating_b_new=1520.0,
            winner="b",
            comparison_id=str(uuid.uuid4()),
        )
    )

    result = runner.invoke(app, ["show", "reader-history", str(mock_site_root_with_db)])

    assert result.exit_code == 0, result.stdout
    assert "🔍 Comparison History" in result.stdout
    assert "post-a" in result.stdout
    assert "post-b" in result.stdout
    assert "post-c" in result.stdout


def test_top_command_no_db(mock_site_root_without_db: Path):
    """Test the 'top' command when the database does not exist."""
    result = runner.invoke(app, ["top", str(mock_site_root_without_db)])

    assert result.exit_code == 1
    assert "Reader database not found" in result.stdout


def test_show_reader_history_command_no_db(mock_site_root_without_db: Path):
    """Test the 'show reader-history' command when the database does not exist."""
    result = runner.invoke(app, ["show", "reader-history", str(mock_site_root_without_db)])

    assert result.exit_code == 1
    assert "Reader database not found" in result.stdout
