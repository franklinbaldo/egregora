from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from egregora.output_sinks.mkdocs.scaffolding import MkDocsSiteScaffolder, safe_yaml_load

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def scaffolder() -> MkDocsSiteScaffolder:
    return MkDocsSiteScaffolder()


def test_about_page_structure_and_styling(tmp_path: Path, scaffolder: MkDocsSiteScaffolder) -> None:
    """
    Verifies that the About page is scaffolded with the correct Glassmorphism structure
    and that the navigation configuration is updated correctly.
    """
    scaffolder.scaffold_site(tmp_path, site_name="Test UX Site")

    # 1. Verify About page content
    about_path = tmp_path / "docs" / "about.md"
    assert about_path.exists()
    content = about_path.read_text(encoding="utf-8")

    # Check for Glassmorphism using Admonition syntax (Robust Fix)
    assert '!!! glass ""' in content

    # Check for Footer
    assert '<div class="homepage-footer">' in content

    # 2. Verify MkDocs Configuration
    mkdocs_path = tmp_path / ".egregora" / "mkdocs.yml"
    assert mkdocs_path.exists()
    mkdocs_config = safe_yaml_load(mkdocs_path.read_text(encoding="utf-8"))

    # Check use_directory_urls
    assert mkdocs_config.get("use_directory_urls") is True

    # Check Navigation Structure
    nav = mkdocs_config.get("nav", [])
    # "About: about.md" should be under Resources
    # Structure is list of dicts: [{'Home': 'index.md'}, {'Resources': [...]}, ...]

    resources_entry = None
    for item in nav:
        if isinstance(item, dict) and "Resources" in item:
            resources_entry = item["Resources"]
            break

    assert resources_entry is not None, "Resources section missing from nav"

    about_entry = None
    for item in resources_entry:
        if isinstance(item, dict) and "About" in item:
            about_entry = item["About"]
            break

    assert about_entry == "about.md", (
        "About page should be navigation item under Resources pointing to about.md"
    )


def test_extra_css_glassmorphism(tmp_path: Path, scaffolder: MkDocsSiteScaffolder) -> None:
    """
    Verifies that the extra.css file contains the glassmorphism styles for .admonition.glass.
    """
    scaffolder.scaffold_site(tmp_path, site_name="Test UX Site")

    css_path = tmp_path / "overrides" / "stylesheets" / "extra.css"
    assert css_path.exists()
    css_content = css_path.read_text(encoding="utf-8")

    assert ".admonition.glass" in css_content
    assert "backdrop-filter: blur" in css_content
