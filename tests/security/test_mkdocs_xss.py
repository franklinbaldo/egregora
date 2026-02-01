import pytest

from egregora.output_sinks.mkdocs.scaffolding import MkDocsSiteScaffolder


def test_html_injection_in_index_md(tmp_path):
    """Verify that site_name is HTML-escaped in generated Markdown files."""
    scaffolder = MkDocsSiteScaffolder()

    # Malicious site name containing HTML tag
    malicious_site_name = "<script>alert(1)</script>"

    # Scaffold the site
    scaffolder.scaffold_site(tmp_path, malicious_site_name)

    # Check docs/index.md
    index_md = tmp_path / "docs" / "index.md"
    content = index_md.read_text(encoding="utf-8")

    # We expect the script tag to be escaped
    # &lt;script&gt;alert(1)&lt;/script&gt;
    if "<script>" in content:
        pytest.fail(
            f"HTML Injection successful! Unescaped tag found in index.md.\nContent snippet:\n{content[:500]}"
        )

    assert "&lt;script&gt;" in content or "&#60;script&#62;" in content
