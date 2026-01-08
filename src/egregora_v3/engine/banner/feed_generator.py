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

from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
)
from egregora.core.types import Document, DocumentType, Entry, Feed

logger = logging.getLogger(__name__)
DEFAULT_TEMPLATE_NAME = "banner.jinja"


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
        output_entries = [
            generate_banner_document(entry, self.provider, self.jinja_env)
            for entry in task_feed.entries
        ]

        return Feed(
            id=f"{task_feed.id}:results",
            title=f"{task_feed.title} - Results",
            updated=datetime.now(UTC),
            entries=output_entries,
            authors=task_feed.authors,
            links=[],
        )


def generate_banner_document(
    entry: Entry,
    provider: ImageGenerationProvider,
    jinja_env: Environment,
) -> Document:
    """Generates a banner document from a single task entry."""
    # 1. Build the prompt from the entry
    template = jinja_env.get_template(DEFAULT_TEMPLATE_NAME)
    prompt = template.render(
        post_title=entry.title,
        post_summary=entry.summary or "",
    )

    # 2. Generate the image
    request = ImageGenerationRequest(
        prompt=prompt,
        response_modalities=["IMAGE"],
        aspect_ratio="1:1",
    )
    result = provider.generate(request)

    # 3. Create the output document
    if result.has_image and result.image_bytes:
        slug = (
            entry.internal_metadata.get("slug")
            if entry.internal_metadata
            else None
        )
        content = base64.b64encode(result.image_bytes).decode("ascii")
        doc = Document(
            doc_type=DocumentType.MEDIA,
            title=f"Banner: {entry.title}",
            content=content,
            internal_metadata={
                "slug": slug,
                "task_id": entry.id,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )
        doc.content_type = result.mime_type or "image/png"
        doc.authors = entry.authors
        return doc
    else:
        # Create an error document on failure
        doc = Document(
            doc_type=DocumentType.NOTE,
            title=f"Error: {entry.title}",
            content=f"Failed to generate banner: {result.error}",
            internal_metadata={
                "task_id": entry.id,
                "error_code": result.error_code,
                "error_message": result.error,
            },
        )
        doc.content_type = "text/plain"
        doc.authors = entry.authors
        return doc
