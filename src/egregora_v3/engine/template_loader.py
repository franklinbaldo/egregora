"""Jinja2 template loader for prompt management.

Provides centralized template loading with custom filters for V3 agents.
"""

from importlib.resources import files
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template

from egregora_v3.core.utils import slugify
from egregora_v3.engine import filters


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
            # Use importlib.resources for robust resource loading
            # Works in both development and packaged deployments
            package_prompts = files("egregora_v3.engine").joinpath("prompts")

            # Convert to Path - resources may return Traversable
            # For packaged apps, this extracts to temp location if needed
            template_dir = Path(str(package_prompts))

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
        self.env.filters["format_datetime"] = filters.format_datetime
        self.env.filters["isoformat"] = filters.isoformat
        self.env.filters["truncate_words"] = filters.truncate_words
        self.env.filters["slugify"] = slugify

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
