"""Tests for TemplateLoader."""
from pathlib import Path

import pytest
from jinja2 import TemplateNotFound

from egregora_v3.core.utils import slugify
from egregora_v3.engine import filters
from egregora_v3.engine.template_loader import TemplateLoader


@pytest.fixture
def template_dir(tmp_path: Path) -> Path:
    """Create a temporary template directory with sample templates."""
    d = tmp_path / "templates"
    d.mkdir()

    # Simple template
    (d / "hello.jinja2").write_text("Hello, {{ name }}!")

    # Template with inheritance
    (d / "base.jinja2").write_text("Base header\n{% block content %}{% endblock %}\nBase footer")
    (d / "child.jinja2").write_text(
        '{% extends "base.jinja2" %}\n{% block content %}Child content{% endblock %}'
    )

    return d


def test_template_loader_initialization(template_dir: Path):
    """Test that TemplateLoader initializes with a custom directory."""
    loader = TemplateLoader(template_dir=template_dir)
    assert loader.template_dir == template_dir


def test_load_template(template_dir: Path):
    """Test that a template can be loaded successfully."""
    loader = TemplateLoader(template_dir=template_dir)
    template = loader.load_template("hello.jinja2")
    assert template is not None
    assert template.render(name="World") == "Hello, World!"


def test_render_template(template_dir: Path):
    """Test rendering a template with context."""
    loader = TemplateLoader(template_dir=template_dir)
    rendered = loader.render_template("hello.jinja2", name="Jinja")
    assert rendered == "Hello, Jinja!"


def test_template_not_found(template_dir: Path):
    """Test that TemplateNotFound is raised for a non-existent template."""
    loader = TemplateLoader(template_dir=template_dir)
    with pytest.raises(TemplateNotFound):
        loader.load_template("non_existent.jinja2")


def test_template_inheritance(template_dir: Path):
    """Test that template inheritance works correctly."""
    loader = TemplateLoader(template_dir=template_dir)
    rendered = loader.render_template("child.jinja2")
    assert "Base header" in rendered
    assert "Child content" in rendered
    assert "Base footer" in rendered


def test_template_loader_registers_custom_filters():
    """Verify that all custom filters are registered."""
    loader = TemplateLoader()
    env = loader.env

    # Heuristic: Data over logic.
    # We define the expected filters declaratively.
    expected_filters = {
        "format_datetime": filters.format_datetime,
        "isoformat": filters.isoformat,
        "truncate_words": filters.truncate_words,
        "slugify": slugify,
    }

    # Assert that all expected filters are present in the environment
    for name, func in expected_filters.items():
        assert name in env.filters
        assert env.filters[name] is func
