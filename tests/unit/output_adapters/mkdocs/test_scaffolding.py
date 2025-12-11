from __future__ import annotations

from pathlib import Path

import pytest

from egregora.output_adapters.mkdocs.scaffolding import MkDocsSiteScaffolder, safe_yaml_load


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
    assert (tmp_path / ".egregora" / "config.yml").exists()


def test_scaffold_site_respects_existing_mkdocs(tmp_path: Path, scaffolder: MkDocsSiteScaffolder) -> None:
    existing_mkdocs = tmp_path / "mkdocs.yml"
    existing_mkdocs.write_text("site_name: Preexisting\nextra: {foo: bar}\n", encoding="utf-8")

    mkdocs_path, created = scaffolder.scaffold_site(tmp_path, site_name="Ignored")

    assert created is False
    assert mkdocs_path == existing_mkdocs
    assert "Preexisting" in existing_mkdocs.read_text(encoding="utf-8")


def test_resolve_paths_returns_site_configuration(tmp_path: Path, scaffolder: MkDocsSiteScaffolder) -> None:
    scaffolder.scaffold_site(tmp_path, site_name="Resolved Site")

    site_config = scaffolder.resolve_paths(tmp_path)

    assert site_config.site_root == tmp_path.resolve()
    assert site_config.site_name == "Resolved Site"
    assert site_config.docs_dir == tmp_path / "docs"
    assert site_config.posts_dir.relative_to(site_config.docs_dir) == Path("blog/posts")
    assert site_config.config_file == tmp_path / ".egregora" / "mkdocs.yml"


def test_main_py_and_overrides_in_egregora_dir(tmp_path: Path, scaffolder: MkDocsSiteScaffolder) -> None:
    """Test that main.py and overrides/ are created in .egregora/ not site root.

    Regression test for PR #1036 - ensures site root stays clean.
    """
    scaffolder.scaffold_site(tmp_path, site_name="Clean Site")

    # main.py should be in .egregora/, not root
    assert (tmp_path / ".egregora" / "main.py").exists()
    assert not (tmp_path / "main.py").exists()

    # overrides/ should be in .egregora/, not root
    assert (tmp_path / ".egregora" / "overrides").exists()
    assert (tmp_path / ".egregora" / "overrides" / "home.html").exists()
    assert not (tmp_path / "overrides").exists()
