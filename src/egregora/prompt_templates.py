"""Jinja2 template management for system prompts.

This module supports custom prompt overrides via .egregora/prompts/ directory.

Priority:
1. .egregora/prompts/ (user overrides)
2. src/egregora/prompts/ (package defaults)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

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

    """
    if site_root:
        user_prompts = site_root / ".egregora" / "prompts"
        if user_prompts.is_dir():
            logger.info("Using custom prompts from %s", user_prompts)
            return user_prompts

    # Fall back to package prompts
    logger.debug("Using package prompts from %s", PACKAGE_PROMPTS_DIR)
    return PACKAGE_PROMPTS_DIR


def create_prompt_environment(site_root: Path | None = None) -> Environment:
    """Create Jinja2 environment with fallback prompt directories.

    Uses FileSystemLoader with priority-based search:
    1. {site_root}/.egregora/prompts/ (custom overrides) - if exists
    2. src/egregora/prompts/ (package defaults) - always included

    This allows users to override individual templates without copying all of them.
    Fresh sites with empty .egregora/prompts/ work out of the box.

    Args:
        site_root: Site root to check for custom prompts

    Returns:
        Configured Jinja2 Environment with fallback search paths

    Examples:
        >>> env = create_prompt_environment(Path("/my/site"))
        >>> template = env.get_template("system/writer.jinja")  # Searches custom then package

    """
    # Build search paths with priority order
    search_paths: list[Path] = []

    # Add custom prompts directory if it exists
    if site_root:
        user_prompts = site_root / ".egregora" / "prompts"
        if user_prompts.is_dir():
            search_paths.append(user_prompts)
            logger.info("Custom prompts directory: %s", user_prompts)

    # Always add package prompts as fallback
    search_paths.append(PACKAGE_PROMPTS_DIR)
    logger.debug("Prompt search paths: %s", search_paths)

    return Environment(
        loader=FileSystemLoader(search_paths),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )


class PromptTemplate(ABC):
    """Base class for prompt templates backed by Jinja files.

    Supports custom prompt overrides via .egregora/prompts/ directory.
    Pass site_root to _render() to enable user overrides.
    """

    template_name: ClassVar[str]

    def _render(
        self,
        env: Environment | None = None,
        site_root: Path | None = None,
        **context: Any,
    ) -> str:
        """Render template with optional custom prompts support.

        Args:
            env: Explicit Jinja2 environment (highest priority)
            site_root: Site root for custom prompts lookup
            **context: Template variables

        Returns:
            Rendered template string

        Priority:
        1. Explicit env parameter
        2. Custom prompts from site_root/.egregora/prompts/
        3. Package default prompts

        """
        # Create environment with custom prompts support
        if env is None and site_root is not None:
            env = create_prompt_environment(site_root)

        template_env = env or DEFAULT_ENVIRONMENT
        template = template_env.get_template(self.template_name)
        return template.render(**context)

    @abstractmethod
    def render(self) -> str:
        """Render the template with the configured context."""


@dataclass(slots=True)
class WriterPromptTemplate(PromptTemplate):
    """Prompt template for the writer agent.

    Supports custom prompts via site_root/.egregora/prompts/system/writer.jinja
    """

    date: str
    markdown_table: str
    active_authors: str
    custom_instructions: str = ""
    markdown_features: str = ""
    profiles_context: str = ""
    rag_context: str = ""
    freeform_memory: str = ""
    enable_memes: bool = False
    site_root: Path | None = None  # For custom prompts
    env: Environment | None = None
    template_name: ClassVar[str] = "system/writer.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
            site_root=self.site_root,
            date=self.date,
            markdown_table=self.markdown_table,
            active_authors=self.active_authors,
            custom_instructions=self.custom_instructions,
            markdown_features=self.markdown_features,
            profiles_context=self.profiles_context,
            rag_context=self.rag_context,
            freeform_memory=self.freeform_memory,
            enable_memes=self.enable_memes,
        )


@dataclass(slots=True)
class UrlEnrichmentPromptTemplate(PromptTemplate):
    """Prompt template for lightweight URL enrichment.

    Supports custom prompts via site_root/.egregora/prompts/enrichment/url_simple.jinja
    """

    url: str
    site_root: Path | None = None
    env: Environment | None = None
    template_name: ClassVar[str] = "enrichment/url_simple.jinja"

    def render(self) -> str:
        return self._render(env=self.env, site_root=self.site_root, url=self.url)


@dataclass(slots=True)
class MediaEnrichmentPromptTemplate(PromptTemplate):
    """Prompt template for lightweight media enrichment.

    Supports custom prompts via site_root/.egregora/prompts/enrichment/media_simple.jinja
    """

    site_root: Path | None = None
    env: Environment | None = None
    template_name: ClassVar[str] = "enrichment/media_simple.jinja"

    def render(self) -> str:
        return self._render(env=self.env, site_root=self.site_root)


@dataclass(slots=True)
class DetailedUrlEnrichmentPromptTemplate(PromptTemplate):
    """Prompt template for detailed URL enrichment.

    Supports custom prompts via site_root/.egregora/prompts/enrichment/url_detailed.jinja
    """

    url: str
    original_message: str
    sender_uuid: str
    date: str
    time: str
    site_root: Path | None = None
    env: Environment | None = None
    template_name: ClassVar[str] = "enrichment/url_detailed.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
            site_root=self.site_root,
            url=self.url,
            original_message=self.original_message,
            sender_uuid=self.sender_uuid,
            date=self.date,
            time=self.time,
        )


@dataclass(slots=True)
class DetailedMediaEnrichmentPromptTemplate(PromptTemplate):
    """Prompt template for detailed media enrichment.

    Supports custom prompts via site_root/.egregora/prompts/enrichment/media_detailed.jinja
    """

    media_type: str
    media_filename: str
    media_path: str
    original_message: str
    sender_uuid: str
    date: str
    time: str
    site_root: Path | None = None
    env: Environment | None = None
    template_name: ClassVar[str] = "enrichment/media_detailed.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
            site_root=self.site_root,
            media_type=self.media_type,
            media_filename=self.media_filename,
            media_path=self.media_path,
            original_message=self.original_message,
            sender_uuid=self.sender_uuid,
            date=self.date,
            time=self.time,
        )


@dataclass(slots=True)
class AvatarEnrichmentPromptTemplate(PromptTemplate):
    """Prompt template for avatar enrichment with moderation.

    Supports custom prompts via site_root/.egregora/prompts/enricher_avatar.jinja
    """

    media_filename: str
    media_path: str
    site_root: Path | None = None
    env: Environment | None = None
    template_name: ClassVar[str] = "enricher_avatar.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
            site_root=self.site_root,
            media_filename=self.media_filename,
            media_path=self.media_path,
        )


@dataclass(slots=True)
class EditorPromptTemplate(PromptTemplate):
    """Prompt template for the editor agent.

    Supports custom prompts via site_root/.egregora/prompts/system/editor.jinja
    """

    post_content: str
    doc_id: str
    version: int
    lines: dict[int, str]
    context: dict[str, Any] | None = None
    site_root: Path | None = None
    env: Environment | None = None
    template_name: ClassVar[str] = "system/editor.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
            site_root=self.site_root,
            post_content=self.post_content,
            doc_id=self.doc_id,
            version=self.version,
            lines=self.lines,
            context=self.context or {},
        )


__all__ = [
    "PACKAGE_PROMPTS_DIR",
    "AvatarEnrichmentPromptTemplate",
    "DetailedMediaEnrichmentPromptTemplate",
    "DetailedUrlEnrichmentPromptTemplate",
    "EditorPromptTemplate",
    "MediaEnrichmentPromptTemplate",
    "PromptTemplate",
    "UrlEnrichmentPromptTemplate",
    "WriterPromptTemplate",
    "create_prompt_environment",
    "find_prompts_dir",
]
