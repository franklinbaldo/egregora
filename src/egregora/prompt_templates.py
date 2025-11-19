"""Jinja2 template management for system prompts.

This module supports custom prompt overrides via .egregora/prompts/ directory.

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
PACKAGE_PROMPTS_DIR = Path(__file__).parent / "prompts"

# Default environment (package prompts only)
DEFAULT_ENVIRONMENT = Environment(
    loader=FileSystemLoader(PACKAGE_PROMPTS_DIR),
    autoescape=select_autoescape(enabled_extensions=()),
    trim_blocks=True,
    lstrip_blocks=True,
)


def find_prompts_dir(site_root: Path | None = None) -> Path:
    """Find prompts directory with user override support.

    Priority:
    1. {site_root}/.egregora/prompts/ (user overrides)
    2. src/egregora/prompts/ (package defaults)

    Args:
        site_root: Site root directory to check for .egregora/

    Returns:
        Path to prompts directory

    Examples:
        >>> find_prompts_dir(Path("/my/site"))
        Path("/my/site/.egregora/prompts")  # if exists
        >>> find_prompts_dir(None)
        Path("src/egregora/prompts")  # fallback

    Note:
        DEPRECATED: Use prompts_dir parameter directly instead.
        Kept for backward compatibility during migration.

    """
    if site_root:
        user_prompts = site_root / ".egregora" / "prompts"
        if user_prompts.is_dir():
            logger.info("Using custom prompts from %s", user_prompts)
            return user_prompts

    # Fall back to package prompts
    logger.debug("Using package prompts from %s", PACKAGE_PROMPTS_DIR)
    return PACKAGE_PROMPTS_DIR


def create_prompt_environment(prompts_dir: Path | None = None) -> Environment:
    """Create Jinja2 environment with fallback prompt directories.

    Uses FileSystemLoader with priority-based search:
    1. {prompts_dir}/ (custom overrides) - if provided and exists
    2. src/egregora/prompts/ (package defaults) - always included

    This allows users to override individual templates without copying all of them.
    Fresh sites with empty .egregora/prompts/ work out of the box.

    Args:
        prompts_dir: Custom prompts directory (e.g., site_root/.egregora/prompts)
                     or site root (will auto-detect .egregora/prompts subdirectory)

    Returns:
        Configured Jinja2 Environment with fallback search paths

    Examples:
        >>> env = create_prompt_environment(Path("/my/site/.egregora/prompts"))
        >>> template = env.get_template("system/writer.jinja")  # Searches custom then package

    """
    # Build search paths with priority order
    search_paths: list[Path] = []

    # Add custom prompts directory if it exists
    if prompts_dir and prompts_dir.is_dir():
        # Check if prompts_dir is a site root with .egregora/prompts subdirectory
        egregora_prompts = prompts_dir / ".egregora" / "prompts"
        if egregora_prompts.is_dir():
            search_paths.append(egregora_prompts)
            logger.info("Custom prompts directory: %s", egregora_prompts)
        else:
            # Use prompts_dir directly
            search_paths.append(prompts_dir)
            logger.info("Custom prompts directory: %s", prompts_dir)

    # Always add package prompts as fallback
    search_paths.append(PACKAGE_PROMPTS_DIR)
    logger.debug("Prompt search paths: %s", search_paths)

    return Environment(
        loader=FileSystemLoader(search_paths),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_prompt(
    template_name: str,
    *,
    env: Environment | None = None,
    prompts_dir: Path | None = None,
    **context: Any,
) -> str:
    """Render a Jinja template with optional custom prompt overrides.

    Args:
        template_name: Template path relative to the prompts directory
        env: Explicit Jinja2 environment (highest priority)
        prompts_dir: Custom prompts directory (e.g., site_root/.egregora/prompts)
        **context: Template variables

    Returns:
        Rendered template string

    Priority:
    1. Explicit env parameter
    2. Custom prompts from prompts_dir
    3. Package default prompts
    """
    template_env = env
    if template_env is None and prompts_dir is not None:
        template_env = create_prompt_environment(prompts_dir)

    template_env = template_env or DEFAULT_ENVIRONMENT
    template = template_env.get_template(template_name)
    return template.render(**context)


__all__ = [
    "PACKAGE_PROMPTS_DIR",
    "create_prompt_environment",
    "find_prompts_dir",
    "render_prompt",
]
