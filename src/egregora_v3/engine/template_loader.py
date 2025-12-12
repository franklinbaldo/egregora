"""Jinja2 template loader for prompt management.

Provides centralized template loading with custom filters for V3 agents.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template


class TemplateLoader:
    """Loads and renders Jinja2 templates for agent prompts.

    Supports:
    - Template inheritance (base templates)
    - Custom filters (datetime formatting, slugify, truncate)
    - Configurable template directory
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialize TemplateLoader.

        Args:
            template_dir: Path to template directory. Defaults to src/egregora_v3/engine/prompts

        """
        if template_dir is None:
            # Default to prompts directory in engine
            template_dir = Path(__file__).parent / "prompts"

        self.template_dir = template_dir

        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=False,  # Prompts are not HTML
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self._register_filters()

    def _register_filters(self) -> None:
        """Register custom Jinja2 filters."""
        self.env.filters["format_datetime"] = self._filter_format_datetime
        self.env.filters["isoformat"] = self._filter_isoformat
        self.env.filters["truncate_words"] = self._filter_truncate_words
        self.env.filters["slugify"] = self._filter_slugify

    @staticmethod
    def _filter_format_datetime(value: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format datetime object.

        Args:
            value: Datetime to format
            format_str: strftime format string

        Returns:
            Formatted datetime string

        """
        if not isinstance(value, datetime):
            return str(value)
        return value.strftime(format_str)

    @staticmethod
    def _filter_isoformat(value: datetime) -> str:
        """Format datetime as ISO 8601.

        Args:
            value: Datetime to format

        Returns:
            ISO 8601 formatted string

        """
        if not isinstance(value, datetime):
            return str(value)
        return value.isoformat()

    @staticmethod
    def _filter_truncate_words(value: str, num_words: int = 50, suffix: str = "...") -> str:
        """Truncate string to specified number of words.

        Args:
            value: String to truncate
            num_words: Maximum number of words
            suffix: Suffix to add if truncated

        Returns:
            Truncated string

        """
        words = value.split()
        if len(words) <= num_words:
            return value

        truncated = " ".join(words[:num_words])
        return f"{truncated}{suffix}"

    @staticmethod
    def _filter_slugify(value: str) -> str:
        """Convert string to URL-safe slug.

        Args:
            value: String to slugify

        Returns:
            Slugified string

        """
        # Convert to lowercase
        slug = value.lower()
        # Replace spaces with hyphens
        slug = re.sub(r"\s+", "-", slug)
        # Remove non-alphanumeric characters (except hyphens)
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        # Remove consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        # Strip leading/trailing hyphens
        return slug.strip("-")

    def load_template(self, template_name: str) -> Template:
        """Load a template by name.

        Args:
            template_name: Template path relative to template_dir (e.g., "writer/system.jinja2")

        Returns:
            Loaded Jinja2 template

        Raises:
            TemplateNotFound: If template does not exist

        """
        return self.env.get_template(template_name)

    def render_template(self, template_name: str, **context: Any) -> str:
        """Load and render a template with context.

        Args:
            template_name: Template path relative to template_dir
            **context: Template context variables

        Returns:
            Rendered template string

        Raises:
            TemplateNotFound: If template does not exist

        """
        template = self.load_template(template_name)
        return template.render(**context)
