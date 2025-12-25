"""Feed-based banner generator for V3 plans.

This module keeps the original feed-to-feed transformation logic so that the
new plan-based pipeline in V3 can reuse it without depending on the V2 queue
implementation.
"""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import cast

from jinja2 import DictLoader, Environment, FileSystemLoader, select_autoescape

from egregora.agents.banner.agent import BannerInput
from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
)
from egregora_v3.core.types import Document, DocumentType, Entry, Feed

logger = logging.getLogger(__name__)
DEFAULT_TEMPLATE_NAME = "banner.jinja"


class BannerTaskEntry:
    """Adapter that exposes Entry metadata as BannerInput fields.

    Feed-based workflows store the parameters for banner generation inside the
    entry's metadata (slug, language, summary, etc.).  This lightweight wrapper
    provides typed accessors so downstream code does not need to know about the
    internal metadata layout of the feed.
    """

    def __init__(self, entry: Entry) -> None:
        self.entry = entry
        self.title = entry.title
        self.summary = entry.summary or ""
        self.slug = (
            entry.internal_metadata.get("slug") if entry.internal_metadata else None
        )
        self.language = (
            entry.internal_metadata.get("language", "pt-BR")
            if entry.internal_metadata
            else "pt-BR"
        )

    def to_banner_input(self) -> BannerInput:
        """Convert task entry to BannerInput for generation."""
        return BannerInput(
            post_title=self.title,
            post_summary=self.summary,
            slug=self.slug,
            language=self.language,
        )


class BannerGenerationResult:
    """Result of processing a single banner task.

    Attributes:
        task_entry: The original feed entry that scheduled the work.
        document: The generated media document (when successful).
        error: Human readable reason for failure (optional).
        error_code: Machine readable code for failure (optional).

    """

    def __init__(
        self,
        task_entry: Entry,
        document: Document | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.task_entry = task_entry
        self.document = document
        self.error = error
        self.error_code = error_code
        self.success = document is not None and error is None


class FeedBannerGenerator:
    """Generates banners from a feed of tasks."""

    def __init__(
        self,
        provider: ImageGenerationProvider,
        prompts_dir: Path | None = None,
    ) -> None:
        """Initialize the feed-based banner generator."""
        self.provider = provider
        self.jinja_env = self._create_environment(prompts_dir)

    def _create_environment(self, configured: Path | None) -> Environment:
        """Create a Jinja environment using either a provided path or packaged defaults."""
        if configured is not None:
            loader = FileSystemLoader(configured)
        else:
            template_text = (
                resources.files("egregora.prompts")
                .joinpath(DEFAULT_TEMPLATE_NAME)
                .read_text(encoding="utf-8")
            )
            loader = DictLoader({DEFAULT_TEMPLATE_NAME: template_text})

        return Environment(
            loader=loader,
            autoescape=select_autoescape(
                enabled_extensions=("jinja", "jinja2", "html", "xml")
            ),
        )

    def generate_from_feed(self, task_feed: Feed) -> Feed:
        """Generate banners from a feed of tasks."""
        results = self._generate_sequential(task_feed.entries)

        output_entries = []
        for result in results:
            if result.success and result.document:
                output_entries.append(result.document)
            else:
                output_entries.append(self._create_error_document(result))

        return Feed(
            id=f"{task_feed.id}:results",
            title=f"{task_feed.title} - Results",
            updated=datetime.now(UTC),
            entries=output_entries,
            authors=task_feed.authors,
            links=[],
        )

    def _generate_sequential(self, entries: list[Entry]) -> list[BannerGenerationResult]:
        """Generate banners sequentially for each task entry."""
        results = []
        for entry in entries:
            task = BannerTaskEntry(entry)
            banner_input = task.to_banner_input()
            result = self._generate_with_provider(task, banner_input)
            results.append(result)
        return results

    def _generate_with_provider(
        self, task: BannerTaskEntry, banner_input: BannerInput
    ) -> BannerGenerationResult:
        """Generate banner using the configured provider."""
        request = ImageGenerationRequest(
            prompt=self._build_prompt(banner_input),
            response_modalities=["IMAGE"],
            aspect_ratio="1:1",
        )

        result = self.provider.generate(request)
        if result.has_image and result.image_bytes:
            document = self._create_media_document(
                task.entry,
                result.image_bytes,
                result.mime_type or "image/png",
            )
            return BannerGenerationResult(task.entry, document=document)
        return BannerGenerationResult(
            task.entry,
            error=result.error or "Unknown error",
            error_code=result.error_code or "GENERATION_FAILED",
        )

    def _build_prompt(self, banner_input: BannerInput) -> str:
        """Build the prompt for banner generation."""
        template = self.jinja_env.get_template("banner.jinja")
        return template.render(
            post_title=banner_input.post_title,
            post_summary=banner_input.post_summary,
        )

    def _create_media_document(
        self, task_entry: Entry, image_data: bytes, mime_type: str
    ) -> Document:
        """Create a MEDIA document for the generated banner."""
        slug = (
            task_entry.internal_metadata.get("slug")
            if task_entry.internal_metadata
            else None
        )
        content = base64.b64encode(image_data).decode("ascii")

        doc = Document.create(
            doc_type=DocumentType.MEDIA,
            title=f"Banner: {task_entry.title}",
            content=content,
            slug=slug,
            internal_metadata={
                "task_id": task_entry.id,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )
        doc.content_type = mime_type
        doc.authors = task_entry.authors
        return doc

    def _create_error_document(self, result: BannerGenerationResult) -> Document:
        """Create an error document for failed generation."""
        doc = Document.create(
            doc_type=DocumentType.NOTE,
            title=f"Error: {result.task_entry.title}",
            content=f"Failed to generate banner: {result.error}",
            internal_metadata={
                "task_id": result.task_entry.id,
                "error_code": result.error_code,
                "error_message": result.error,
            },
        )
        doc.content_type = "text/plain"
        doc.authors = result.task_entry.authors
        return doc
