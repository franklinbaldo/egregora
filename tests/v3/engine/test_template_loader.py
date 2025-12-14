"""Tests for Jinja2 template loader.

Following TDD approach - tests written before implementation.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from jinja2 import TemplateNotFound

from egregora_v3.engine.template_loader import TemplateLoader


class TestTemplateLoaderBasics:
    """Test basic TemplateLoader functionality."""

    def test_template_loader_initializes_with_default_path(self) -> None:
        """TemplateLoader should initialize with default prompts directory."""
        loader = TemplateLoader()
        assert loader.template_dir is not None
        assert loader.template_dir.name == "prompts"

    def test_template_loader_initializes_with_custom_path(self, tmp_path: Path) -> None:
        """TemplateLoader should initialize with custom template directory."""
        custom_dir = tmp_path / "custom_prompts"
        custom_dir.mkdir()

        loader = TemplateLoader(template_dir=custom_dir)
        assert loader.template_dir == custom_dir

    def test_template_loader_creates_jinja2_environment(self) -> None:
        """TemplateLoader should create a Jinja2 Environment."""
        loader = TemplateLoader()
        assert loader.env is not None
        assert hasattr(loader.env, "get_template")


class TestTemplateLoading:
    """Test template loading functionality."""

    @pytest.fixture
    def template_dir(self, tmp_path: Path) -> Path:
        """Create a temporary template directory with sample templates."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Create a simple template
        writer_dir = prompts_dir / "writer"
        writer_dir.mkdir()

        system_template = writer_dir / "system.jinja2"
        system_template.write_text("You are a helpful writing assistant.\nCurrent date: {{ current_date }}")

        generate_template = writer_dir / "generate_post.jinja2"
        generate_template.write_text(
            "Generate a blog post about:\nTitle: {{ entry.title }}\nContent: {{ entry.content }}"
        )

        return prompts_dir

    def test_load_template_success(self, template_dir: Path) -> None:
        """TemplateLoader should load existing templates."""
        loader = TemplateLoader(template_dir=template_dir)
        template = loader.load_template("writer/system.jinja2")

        assert template is not None
        assert "helpful writing assistant" in template.render(current_date="2024-12-12")

    def test_load_template_not_found(self, template_dir: Path) -> None:
        """TemplateLoader should raise TemplateNotFound for missing templates."""
        loader = TemplateLoader(template_dir=template_dir)

        with pytest.raises(TemplateNotFound):
            loader.load_template("nonexistent/template.jinja2")

    def test_render_template_with_context(self, template_dir: Path) -> None:
        """TemplateLoader should render templates with context variables."""
        loader = TemplateLoader(template_dir=template_dir)

        class MockEntry:
            title = "Test Post"
            content = "Test content"

        result = loader.render_template("writer/generate_post.jinja2", entry=MockEntry())

        assert "Test Post" in result
        assert "Test content" in result


class TestCustomFilters:
    """Test custom Jinja2 filters."""

    @pytest.fixture
    def template_dir(self, tmp_path: Path) -> Path:
        """Create a temporary template directory with filter usage."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        test_dir = prompts_dir / "test"
        test_dir.mkdir()

        # Template using custom filters
        filter_template = test_dir / "filters.jinja2"
        filter_template.write_text(
            "Formatted date: {{ date | format_datetime }}\n"
            "ISO date: {{ date | isoformat }}\n"
            "Truncated: {{ text | truncate_words(5) }}\n"
            "Slug: {{ title | slugify }}"
        )

        return prompts_dir

    def test_format_datetime_filter(self, template_dir: Path) -> None:
        """TemplateLoader should have format_datetime filter."""
        loader = TemplateLoader(template_dir=template_dir)

        test_date = datetime(2024, 12, 12, 15, 30, 0, tzinfo=UTC)
        result = loader.render_template(
            "test/filters.jinja2",
            date=test_date,
            text="One two three four five six seven",
            title="Hello World Example",
        )

        # format_datetime should format date nicely
        assert "2024" in result
        assert "12" in result

    def test_isoformat_filter(self, template_dir: Path) -> None:
        """TemplateLoader should have isoformat filter."""
        loader = TemplateLoader(template_dir=template_dir)

        test_date = datetime(2024, 12, 12, 15, 30, 0, tzinfo=UTC)
        result = loader.render_template(
            "test/filters.jinja2",
            date=test_date,
            text="One two three four five six seven",
            title="Hello World Example",
        )

        # isoformat should produce ISO 8601 format
        assert "2024-12-12T15:30:00" in result

    def test_truncate_words_filter(self, template_dir: Path) -> None:
        """TemplateLoader should have truncate_words filter."""
        loader = TemplateLoader(template_dir=template_dir)

        test_date = datetime(2024, 12, 12, 15, 30, 0, tzinfo=UTC)
        result = loader.render_template(
            "test/filters.jinja2",
            date=test_date,
            text="One two three four five six seven",
            title="Hello World Example",
        )

        # truncate_words(5) should keep first 5 words
        assert "One two three four five" in result
        assert "six" not in result or "..." in result

    def test_slugify_filter(self, template_dir: Path) -> None:
        """TemplateLoader should have slugify filter."""
        loader = TemplateLoader(template_dir=template_dir)

        test_date = datetime(2024, 12, 12, 15, 30, 0, tzinfo=UTC)
        result = loader.render_template(
            "test/filters.jinja2",
            date=test_date,
            text="One two three four five six seven",
            title="Hello World Example",
        )

        # slugify should convert to URL-safe slug
        assert "hello-world-example" in result


class TestTemplateInheritance:
    """Test Jinja2 template inheritance."""

    @pytest.fixture
    def template_dir(self, tmp_path: Path) -> Path:
        """Create template directory with base template."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Base template
        base_template = prompts_dir / "base.jinja2"
        base_template.write_text(
            "You are a helpful AI assistant.\n\n"
            "{% block instructions %}{% endblock %}\n\n"
            "Current date: {{ current_date }}"
        )

        # Child template
        writer_dir = prompts_dir / "writer"
        writer_dir.mkdir()
        child_template = writer_dir / "child.jinja2"
        child_template.write_text(
            "{% extends 'base.jinja2' %}\n{% block instructions %}\nGenerate a blog post.\n{% endblock %}"
        )

        return prompts_dir

    def test_template_inheritance_works(self, template_dir: Path) -> None:
        """TemplateLoader should support Jinja2 template inheritance."""
        loader = TemplateLoader(template_dir=template_dir)

        result = loader.render_template("writer/child.jinja2", current_date="2024-12-12")

        # Should contain base template content
        assert "helpful AI assistant" in result
        # Should contain child template content
        assert "Generate a blog post" in result
        # Should contain variable substitution
        assert "2024-12-12" in result
