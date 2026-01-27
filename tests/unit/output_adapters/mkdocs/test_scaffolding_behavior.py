from __future__ import annotations

from typing import TYPE_CHECKING

from egregora.output_sinks.mkdocs.scaffolding import (
    MkDocsSiteScaffolder,
    ensure_mkdocs_project,
    safe_yaml_load,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_safe_yaml_load_ignores_unknown_tags():
    """Test that safe_yaml_load ignores unknown tags like !ENV."""
    yaml_content = """
    site_name: Test Site
    site_url: !ENV "SITE_URL"
    plugins:
      - search
    """
    data = safe_yaml_load(yaml_content)

    # Standard yaml.safe_load would raise ConstructorError
    # Our loader should parse it, but !ENV "SITE_URL" might be parsed as None or similar depending on implementation
    # The implementation says: _ConfigLoader.add_constructor(None, lambda loader, _node: None)
    # This means unknown tags result in None.

    assert data["site_name"] == "Test Site"
    assert data["site_url"] is None
    assert data["plugins"] == ["search"]


def test_ensure_mkdocs_project_creates_site(tmp_path: Path):
    """Test that ensure_mkdocs_project calls scaffolding and returns docs dir."""
    site_root = tmp_path / "mysite"
    site_root.mkdir()

    docs_dir, created = ensure_mkdocs_project(site_root, site_name="My Site")

    assert created is True
    assert docs_dir == site_root / "docs"
    assert (site_root / ".egregora" / "mkdocs.yml").exists()

    # Verify idempotent
    docs_dir_2, created_2 = ensure_mkdocs_project(site_root, site_name="My Site")
    assert created_2 is False
    assert docs_dir_2 == docs_dir


def test_scaffold_wrapper_method(tmp_path: Path):
    """Test the scaffold() wrapper method with config dict."""
    scaffolder = MkDocsSiteScaffolder()
    site_root = tmp_path / "wrapper_site"
    config = {"site_name": "Wrapper Site"}

    scaffolder.scaffold(site_root, config)

    assert (site_root / ".egregora" / "mkdocs.yml").exists()
    mkdocs_content = (site_root / ".egregora" / "mkdocs.yml").read_text()
    assert "site_name: Wrapper Site" in mkdocs_content


def test_scaffold_authors_file_creation(tmp_path: Path):
    """Test that _scaffold_authors_file creates .authors.yml if missing."""
    scaffolder = MkDocsSiteScaffolder()
    site_root = tmp_path / "authors_test"
    site_root.mkdir()

    # We can test this by calling scaffold_site which calls _scaffold_authors_file
    scaffolder.scaffold_site(site_root, site_name="Authors Test")

    authors_file = site_root / "docs" / ".authors.yml"
    assert authors_file.exists()
    assert "# Authors metadata" in authors_file.read_text()

    # Modify it
    authors_file.write_text("existing: true")

    # Run again, should not overwrite
    scaffolder.scaffold_site(site_root, site_name="Authors Test")
    assert "existing: true" in authors_file.read_text()


def test_supports_site_detection(tmp_path: Path):
    """Test supports_site returns True only if .egregora/mkdocs.yml exists."""
    scaffolder = MkDocsSiteScaffolder()
    site_root = tmp_path / "detection_test"
    site_root.mkdir()

    # Empty dir
    assert scaffolder.supports_site(site_root) is False

    # MkDocs in root (wrong place)
    (site_root / "mkdocs.yml").touch()
    assert scaffolder.supports_site(site_root) is False

    # Correct place
    (site_root / ".egregora").mkdir()
    (site_root / ".egregora" / "mkdocs.yml").touch()
    assert scaffolder.supports_site(site_root) is True
