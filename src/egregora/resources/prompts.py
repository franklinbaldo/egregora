"""Centralized prompt template management.

This module replaces `egregora.prompt_templates` and provides:
- Unified `PromptManager` class
- Logic for resolving prompt overrides (User > Package)
- Helper for copying default prompts to a new site

Priority:
1. .egregora/prompts/ (user overrides)
2. src/egregora/prompts/ (package defaults)
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Package default prompts directory
# Resolves to src/egregora/prompts
PACKAGE_PROMPTS_DIR = Path(__file__).parents[1] / "prompts"


class PromptManager:
    """Manages Jinja2 environment for prompts with override support."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        """Initialize prompt manager.

        Args:
            prompts_dir: Optional custom prompts directory (e.g., site/.egregora/prompts).
                         If provided, it takes precedence over package defaults.
        """
        self.prompts_dir = prompts_dir
        self.env = self._create_environment()

    def _create_environment(self) -> Environment:
        """Create Jinja2 environment with fallback prompt directories."""
        search_paths: list[Path] = []

        # Add custom prompts directory if it exists
        if self.prompts_dir and self.prompts_dir.is_dir():
            # Check if prompts_dir is a site root with .egregora/prompts subdirectory
            # This handles cases where user passes site_root instead of prompts_dir
            egregora_prompts = self.prompts_dir / ".egregora" / "prompts"
            if egregora_prompts.is_dir():
                search_paths.append(egregora_prompts)
                logger.debug("Using custom prompts from: %s", egregora_prompts)
            else:
                search_paths.append(self.prompts_dir)
                logger.debug("Using custom prompts from: %s", self.prompts_dir)

        # Always add package prompts as fallback
        if PACKAGE_PROMPTS_DIR.is_dir():
            search_paths.append(PACKAGE_PROMPTS_DIR)
        else:
            logger.warning("Package prompts directory not found at %s", PACKAGE_PROMPTS_DIR)

        logger.debug("Prompt search paths: %s", search_paths)

        return Environment(
            loader=FileSystemLoader(search_paths),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **context: Any) -> str:
        """Render a prompt template.

        Args:
            template_name: Name of the template (e.g., "system/writer.jinja")
            **context: Variables to pass to the template

        Returns:
            Rendered string
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

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

            # Only copy if target doesn't exist (preserve customizations)
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
_default_manager = PromptManager()


def render_prompt(
    template_name: str,
    *,
    prompts_dir: Path | None = None,
    **context: Any,
) -> str:
    """Helper function to render a prompt without managing instance lifecycle.

    This maintains API compatibility with the old `prompt_templates.py`.
    """
    if prompts_dir:
        manager = PromptManager(prompts_dir)
    else:
        manager = _default_manager

    return manager.render(template_name, **context)
