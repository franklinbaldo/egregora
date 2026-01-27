from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from jinja2 import TemplateError
from yaml import YAMLError

from egregora.output_sinks.exceptions import (
    ConfigLoadError,
    FileSystemScaffoldError,
    PathResolutionError,
    ScaffoldingError,
    SiteNotSupportedError,
    TemplateRenderingError,
)
from egregora.output_sinks.mkdocs.scaffolding import MkDocsSiteScaffolder, safe_yaml_load

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def scaffolder() -> MkDocsSiteScaffolder:
    return MkDocsSiteScaffolder()


def test_scaffold_site_creates_expected_layout(tmp_path: Path, scaffolder: MkDocsSiteScaffolder) -> None:
    mkdocs_path, created = scaffolder.scaffold_site(tmp_path, site_name="Test Site")

    assert created is True
    assert mkdocs_path == tmp_path / ".egregora" / "mkdocs.yml"
    assert mkdocs_path.exists()

    mkdocs_config = safe_yaml_load(mkdocs_path.read_text(encoding="utf-8"))
    assert mkdocs_config.get("site_name") == "Test Site"

    docs_dir = tmp_path / "docs"
    assert docs_dir.exists()
    assert (docs_dir / "index.md").exists()
    assert (tmp_path / ".egregora.toml").exists()


def test_resolve_paths_returns_site_configuration(tmp_path: Path, scaffolder: MkDocsSiteScaffolder) -> None:
    scaffolder.scaffold_site(tmp_path, site_name="Resolved Site")

    site_config = scaffolder.resolve_paths(tmp_path)

    assert site_config.site_root == tmp_path.resolve()
    assert site_config.site_name == "Resolved Site"
    assert site_config.docs_dir == tmp_path / "docs"
    assert site_config.posts_dir == site_config.docs_dir / "posts"
    assert site_config.config_file == tmp_path / ".egregora" / "mkdocs.yml"


def test_overrides_are_in_site_root(tmp_path: Path, scaffolder: MkDocsSiteScaffolder) -> None:
    """Test that overrides/ is created in the site root."""
    scaffolder.scaffold_site(tmp_path, site_name="Clean Site")

    overrides_dir = tmp_path / "overrides"
    assert overrides_dir.exists()
    assert overrides_dir.is_dir()
    assert not (tmp_path / ".egregora" / "overrides").exists()


def test_scaffold_site_raises_template_rendering_error(scaffolder: MkDocsSiteScaffolder, tmp_path: Path):
    """Test that scaffold_site raises TemplateRenderingError on a Jinja2 error."""
    site_root = tmp_path / "test_site"
    site_name = "Test Site"

    with patch("jinja2.Environment.get_template", side_effect=TemplateError("Test template error")):
        with pytest.raises(TemplateRenderingError) as excinfo:
            scaffolder.scaffold_site(site_root, site_name)

    assert "Failed to render template" in str(excinfo.value)
    assert "Test template error" in str(excinfo.value)


def test_scaffold_site_raises_filesystem_scaffold_error(scaffolder: MkDocsSiteScaffolder, tmp_path: Path):
    """Test that scaffold_site raises FileSystemScaffoldError on an OSError."""
    site_root = tmp_path / "test_site"
    site_name = "Test Site"

    with patch("pathlib.Path.write_text", side_effect=OSError("Test OS error")):
        with pytest.raises(FileSystemScaffoldError) as excinfo:
            scaffolder.scaffold_site(site_root, site_name)

    assert "File system operation 'write' failed" in str(excinfo.value)
    assert "Test OS error" in str(excinfo.value)


def test_resolve_paths_raises_config_load_error(scaffolder: MkDocsSiteScaffolder, tmp_path: Path):
    """Test that resolve_paths raises ConfigLoadError on a YAMLError."""
    site_root = tmp_path / "test_site"
    (site_root / ".egregora" / "mkdocs.yml").parent.mkdir(parents=True)
    (site_root / ".egregora" / "mkdocs.yml").touch()

    with patch(
        "egregora.output_sinks.mkdocs.scaffolding.safe_yaml_load", side_effect=YAMLError("Test YAML error")
    ):
        with pytest.raises(ConfigLoadError) as excinfo:
            scaffolder.resolve_paths(site_root)

    assert "Failed to load or parse config" in str(excinfo.value)
    assert "Test YAML error" in str(excinfo.value)


def test_resolve_paths_raises_path_resolution_error(scaffolder: MkDocsSiteScaffolder, tmp_path: Path):
    """Test that resolve_paths raises PathResolutionError on a general error."""
    site_root = tmp_path / "test_site"
    (site_root / ".egregora" / "mkdocs.yml").parent.mkdir(parents=True)
    (site_root / ".egregora" / "mkdocs.yml").touch()

    with patch(
        "egregora.output_sinks.mkdocs.paths.MkDocsPaths.__init__", side_effect=Exception("Test path error")
    ):
        with pytest.raises(PathResolutionError) as excinfo:
            scaffolder.resolve_paths(site_root)

    assert "Failed to resolve paths for site" in str(excinfo.value)
    assert "Test path error" in str(excinfo.value)


def test_scaffold_site_raises_scaffolding_error_on_unexpected_exception(
    scaffolder: MkDocsSiteScaffolder, tmp_path: Path
):
    """Test that scaffold_site raises ScaffoldingError on an unexpected exception."""
    site_root = tmp_path / "test_site"
    site_name = "Test Site"

    with patch(
        "egregora.output_sinks.mkdocs.scaffolding.MkDocsSiteScaffolder._create_site_structure",
        side_effect=Exception("Unexpected error"),
    ):
        with pytest.raises(ScaffoldingError) as excinfo:
            scaffolder.scaffold_site(site_root, site_name)

    assert "An unexpected error occurred during scaffolding" in str(excinfo.value)
    assert "Unexpected error" in str(excinfo.value)


def test_resolve_paths_raises_site_not_supported_error_for_invalid_site(
    scaffolder: MkDocsSiteScaffolder, tmp_path: Path
):
    """Test that resolve_paths raises SiteNotSupportedError for an invalid site."""
    invalid_site_root = tmp_path / "invalid_site"
    invalid_site_root.mkdir()

    with pytest.raises(SiteNotSupportedError) as excinfo:
        scaffolder.resolve_paths(invalid_site_root)

    assert "is not a supported site" in str(excinfo.value)
