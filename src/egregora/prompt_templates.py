"""Jinja2 template management for system prompts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from jinja2 import Environment, FileSystemLoader, select_autoescape

PROMPTS_DIR = Path(__file__).parent / "prompts"
DEFAULT_ENVIRONMENT = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    autoescape=select_autoescape(enabled_extensions=()),
    trim_blocks=True,
    lstrip_blocks=True,
)


class PromptTemplate(ABC):
    """Base class for prompt templates backed by Jinja files."""

    template_name: ClassVar[str]

    def _render(self, env: Environment | None = None, **context: Any) -> str:
        template_env = env or DEFAULT_ENVIRONMENT
        template = template_env.get_template(self.template_name)
        return template.render(**context)

    @abstractmethod
    def render(self) -> str:
        """Render the template with the configured context."""


@dataclass(slots=True)
class WriterPromptTemplate(PromptTemplate):
    """Prompt template for the writer agent."""

    date: str
    markdown_table: str
    active_authors: str
    custom_instructions: str = ""
    markdown_features: str = ""
    profiles_context: str = ""
    rag_context: str = ""
    freeform_memory: str = ""
    enable_memes: bool = False
    env: Environment | None = None
    template_name: ClassVar[str] = "system/writer.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
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
    """Prompt template for lightweight URL enrichment."""

    url: str
    env: Environment | None = None
    template_name: ClassVar[str] = "enrichment/url_simple.jinja"

    def render(self) -> str:
        return self._render(env=self.env, url=self.url)


@dataclass(slots=True)
class MediaEnrichmentPromptTemplate(PromptTemplate):
    """Prompt template for lightweight media enrichment."""

    env: Environment | None = None
    template_name: ClassVar[str] = "enrichment/media_simple.jinja"

    def render(self) -> str:
        return self._render(env=self.env)


@dataclass(slots=True)
class DetailedUrlEnrichmentPromptTemplate(PromptTemplate):
    """Prompt template for detailed URL enrichment."""

    url: str
    original_message: str
    sender_uuid: str
    date: str
    time: str
    env: Environment | None = None
    template_name: ClassVar[str] = "enrichment/url_detailed.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
            url=self.url,
            original_message=self.original_message,
            sender_uuid=self.sender_uuid,
            date=self.date,
            time=self.time,
        )


@dataclass(slots=True)
class DetailedMediaEnrichmentPromptTemplate(PromptTemplate):
    """Prompt template for detailed media enrichment."""

    media_type: str
    media_filename: str
    media_path: str
    original_message: str
    sender_uuid: str
    date: str
    time: str
    env: Environment | None = None
    template_name: ClassVar[str] = "enrichment/media_detailed.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
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
    """Prompt template for avatar enrichment with moderation."""

    media_filename: str
    media_path: str
    env: Environment | None = None
    template_name: ClassVar[str] = "enricher_avatar.jinja"

    def render(self) -> str:
        return self._render(env=self.env, media_filename=self.media_filename, media_path=self.media_path)


@dataclass(slots=True)
class EditorPromptTemplate(PromptTemplate):
    """Prompt template for the editor agent."""

    post_content: str
    doc_id: str
    version: int
    lines: dict[int, str]
    context: dict[str, Any] | None = None
    env: Environment | None = None
    template_name: ClassVar[str] = "system/editor.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
            post_content=self.post_content,
            doc_id=self.doc_id,
            version=self.version,
            lines=self.lines,
            context=self.context or {},
        )


__all__ = [
    "AvatarEnrichmentPromptTemplate",
    "DetailedMediaEnrichmentPromptTemplate",
    "DetailedUrlEnrichmentPromptTemplate",
    "EditorPromptTemplate",
    "MediaEnrichmentPromptTemplate",
    "PromptTemplate",
    "UrlEnrichmentPromptTemplate",
    "WriterPromptTemplate",
]
