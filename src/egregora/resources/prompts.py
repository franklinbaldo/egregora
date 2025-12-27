"""Centralized prompt template management.

This module replaces `egregora.prompt_templates` and provides:
- `TemplateLoader` for resolving prompt search paths
- `PromptManager` for rendering Jinja2 templates
- Logic for resolving prompt overrides (User > Package)
- Helper for copying default prompts to a new site

Priority:
1. .egregora/prompts/ (user overrides)
2. src/egregora/prompts/ (package defaults)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Package default prompts directory
# Resolves to src/egregora/prompts
PACKAGE_PROMPTS_DIR = Path(__file__).parents[1] / "prompts"


class TemplateLoader:
    """Resolves and provides search paths for Jinja2 templates."""

    def __init__(self, site_dir: Path | None = None) -> None:
        """Initialize template loader.

        Args:
            site_dir: Optional custom prompts directory (e.g., site root).
                         If provided, it takes precedence over package defaults.
        """
        self.site_dir = site_dir
        self.search_paths = self._resolve_search_paths()

    def _resolve_search_paths(self) -> list[Path]:
        """Get the ordered list of directories to search for templates."""
        search_paths: list[Path] = []

        if self.site_dir and self.site_dir.is_dir():
            egregora_prompts = self.site_dir / ".egregora" / "prompts"
            if egregora_prompts.is_dir():
                search_paths.append(egregora_prompts)
                logger.debug("Using custom prompts from: %s", egregora_prompts)
            else:
                search_paths.append(self.site_dir)
                logger.debug("Using custom prompts from: %s", self.site_dir)

        if PACKAGE_PROMPTS_DIR.is_dir():
            search_paths.append(PACKAGE_PROMPTS_DIR)
        else:
            logger.warning("Package prompts directory not found at %s", PACKAGE_PROMPTS_DIR)

        logger.debug("Prompt search paths: %s", search_paths)
        return search_paths

    def get_template_content(self, template_name: str) -> str:
        """Retrieve raw content of a template from the resolved search paths.

        Used for signature generation (hashing logic) without rendering.

        Args:
            template_name: Name of the template (e.g. "writer.jinja")

        Returns:
            Raw template content string
        """
        for search_path in self.search_paths:
            template_path = search_path / template_name
            if template_path.exists():
                return template_path.read_text(encoding="utf-8")

        logger.warning("Template '%s' not found in search paths: %s", template_name, self.search_paths)
        return ""


class PromptManager:
    """Manages Jinja2 environment for prompts with override support."""

    def __init__(self, search_paths: list[Path]) -> None:
        """Initialize prompt manager.

        Args:
            search_paths: A list of paths to search for templates, in order of priority.
        """
        self.search_paths = search_paths
        self.env = self._create_environment()

    def _create_environment(self) -> Environment:
        """Create Jinja2 environment with fallback prompt directories."""
        return Environment(
            loader=FileSystemLoader(self.search_paths),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **context: Any) -> str:
        """Render a prompt template.

        Args:
            template_name: Name of the template (e.g., "writer.jinja")
            **context: Variables to pass to the template

        Returns:
            Rendered string
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    @staticmethod
    def get_template_content(template_name: str, site_dir: Path | None = None) -> str:
        """Retrieve raw content of a template, prioritizing custom overrides.

        This is a convenience static method. For heavy use, create a TemplateLoader instance.

        Args:
            template_name: Name of the template (e.g. "writer.jinja")
            site_dir: Optional directory for user overrides

        Returns:
            Raw template content string
        """
        loader = TemplateLoader(site_dir)
        return loader.get_template_content(template_name)

    @staticmethod
    def copy_defaults(target_dir: Path) -> int:
        """Copy default prompt templates from package to target directory.

        Implements "version pinning": prompts are copied once during init and become site-specific.

        Args:
            target_dir: Destination directory (e.g. .egregora/prompts/)

        Returns:
            Number of files copied
        """
        if not PACKAGE_PROMPTS_DIR.exists():
            logger.warning("Package prompts directory not found: %s", PACKAGE_PROMPTS_DIR)
            return 0

        copied_count = 0
        target_dir.mkdir(parents=True, exist_ok=True)

        for source_file in PACKAGE_PROMPTS_DIR.rglob("*.jinja"):
            rel_path = source_file.relative_to(PACKAGE_PROMPTS_DIR)
            target_file = target_dir / rel_path

            if not target_file.exists():
                target_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target_file.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")
                    copied_count += 1
                except (OSError, UnicodeDecodeError) as e:
                    logger.warning("Failed to copy prompt %s: %s", source_file.name, e)

        if copied_count > 0:
            logger.info("Copied %d default prompt templates to %s", copied_count, target_dir)

        return copied_count


# Global instance for simple use cases (package defaults only)
_default_loader = TemplateLoader()
_default_manager = PromptManager(_default_loader.search_paths)


def render_prompt(
    template_name: str,
    *,
    site_dir: Path | None = None,
    **context: Any,
) -> str:
    """Helper function to render a prompt without managing instance lifecycle.

    This maintains API compatibility with the old `prompt_templates.py`.
    """
    if site_dir:
        loader = TemplateLoader(site_dir)
        manager = PromptManager(loader.search_paths)
    else:
        manager = _default_manager

    return manager.render(template_name, **context)
