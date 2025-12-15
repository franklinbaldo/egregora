
import pytest
from pathlib import Path
from egregora.utils.frontmatter_utils import read_frontmatter_only

def test_read_frontmatter_only_basic(tmp_path):
    p = tmp_path / "test.md"
    p.write_text("---\ntitle: Hello\nauthors: [a, b]\n---\nContent", encoding="utf-8")

    fm = read_frontmatter_only(p)
    assert fm["title"] == "Hello"
    assert fm["authors"] == ["a", "b"]

def test_read_frontmatter_only_large_file(tmp_path):
    p = tmp_path / "large.md"
    frontmatter = "---\ntitle: Large\n---\n"
    content = "A" * 1024 * 1024
    p.write_text(frontmatter + content, encoding="utf-8")

    fm = read_frontmatter_only(p)
    assert fm["title"] == "Large"

def test_read_frontmatter_only_no_frontmatter(tmp_path):
    p = tmp_path / "no_fm.md"
    p.write_text("Just content", encoding="utf-8")
    fm = read_frontmatter_only(p)
    assert fm == {}

def test_read_frontmatter_only_invalid_yaml(tmp_path):
    p = tmp_path / "invalid.md"
    p.write_text("---\ntitle: [unclosed list\n---\n", encoding="utf-8")
    fm = read_frontmatter_only(p)
    assert fm == {}

def test_read_frontmatter_only_empty_file(tmp_path):
    p = tmp_path / "empty.md"
    p.write_text("", encoding="utf-8")
    fm = read_frontmatter_only(p)
    assert fm == {}
