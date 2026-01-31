import pytest
from pathlib import Path
import re

@pytest.fixture
def template_dir():
    # Helper to find the template directory relative to the repo root
    # Adjust path assuming tests run from repo root
    return Path("src/egregora/rendering/templates/site")

def test_mkdocs_privacy_no_external_requests(template_dir):
    """
    Verify that mkdocs.yml.jinja and extra.css do not contain external calls
    to known tracking domains (Google Fonts, unpkg, etc).
    """
    mkdocs_template = template_dir / "mkdocs.yml.jinja"
    css_file = template_dir / "overrides/stylesheets/extra.css"

    assert mkdocs_template.exists(), f"mkdocs.yml.jinja not found at {mkdocs_template}"
    assert css_file.exists(), f"extra.css not found at {css_file}"

    forbidden_patterns = [
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "unpkg.com",
        "cdn.jsdelivr.net",
        "cloudflare.com",
    ]

    # Check mkdocs.yml.jinja
    content = mkdocs_template.read_text(encoding="utf-8")
    for pattern in forbidden_patterns:
        assert pattern not in content, f"Found forbidden external link '{pattern}' in mkdocs.yml.jinja"

    # Check extra.css
    content = css_file.read_text(encoding="utf-8")
    for pattern in forbidden_patterns:
        assert pattern not in content, f"Found forbidden external link '{pattern}' in extra.css"

def test_mkdocs_font_configuration(template_dir):
    """
    Verify that mkdocs.yml.jinja disables automatic font fetching (font: false).
    """
    mkdocs_template = template_dir / "mkdocs.yml.jinja"
    content = mkdocs_template.read_text(encoding="utf-8")

    # Check that font is set to false
    assert re.search(r"font:\s*false", content), "Theme font should be set to false to prevent Google Fonts requests"

def test_mkdocs_no_offline_plugin(template_dir):
    """
    Verify that mkdocs-offline plugin is NOT used as it triggers external requests to unpkg.com.
    """
    mkdocs_template = template_dir / "mkdocs.yml.jinja"
    content = mkdocs_template.read_text(encoding="utf-8")

    # Check that ' - offline' is not in plugins
    assert not re.search(r"^\s*-\s*offline\s*$", content, re.MULTILINE), "Offline plugin should be removed for privacy"
