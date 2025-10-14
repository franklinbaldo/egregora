"""Tests for the static site builder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from egregora.config import PipelineConfig
from egregora.static.builder import StaticSiteBuilder


@pytest.fixture
def site_builder(tmp_path: Path) -> StaticSiteBuilder:
    """Returns a StaticSiteBuilder instance with a temporary posts_dir."""
    config = PipelineConfig(posts_dir=tmp_path)
    return StaticSiteBuilder(config)


def test_generate_mkdocs_config(site_builder: StaticSiteBuilder):
    """Tests that the mkdocs.yml file is generated correctly."""
    site_builder.generate_mkdocs_config()
    config_path = site_builder.mkdocs_config_path
    assert config_path.exists()
    with open(config_path) as f:
        config = yaml.safe_load(f)
    assert config["site_name"] == "Egregora"
    assert config["theme"] == "material"
    assert config["nav"] == [{"Home": "index.md"}]


def test_prepare_docs(site_builder: StaticSiteBuilder):
    """Tests that the docs directory is prepared correctly."""
    # Create some dummy post files
    posts_dir = site_builder.config.posts_dir
    (posts_dir / "2025-10-13.md").write_text("Test post 1")
    (posts_dir / "2025-10-12.md").write_text("Test post 2")

    site_builder.prepare_docs()

    docs_dir = posts_dir / "docs"
    assert (docs_dir / "index.md").exists()
    assert (docs_dir / "posts" / "2025-10-13.md").exists()
    assert (docs_dir / "posts" / "2025-10-12.md").exists()

    index_content = (docs_dir / "index.md").read_text()
    assert "[2025-10-13](posts/2025-10-13.md)" in index_content
    assert "[2025-10-12](posts/2025-10-12.md)" in index_content


@patch("subprocess.run")
def test_build_and_serve(mock_run, site_builder: StaticSiteBuilder):
    """Tests that the build and serve methods call the correct mkdocs commands."""
    site_builder.build()
    mock_run.assert_called_with(
        ["mkdocs", "build", "-f", str(site_builder.mkdocs_config_path)]
    )

    site_builder.serve()
    mock_run.assert_called_with(
        ["mkdocs", "serve", "-a", "0.0.0.0:8001", "-f", str(site_builder.mkdocs_config_path)]
    )
