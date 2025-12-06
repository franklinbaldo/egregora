"""Feed-based banner generator (v3).

This module implements a feed-to-feed transformation for banner generation:
- Input: Feed with entries representing banner generation tasks
- Output: Feed with entries representing generated banners (MEDIA documents)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from egregora.agents.banner.agent import BannerInput, generate_banner
from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
)
from egregora_v3.core.types import Document, DocumentType, Entry, Feed


class BannerTaskEntry:
    """Represents a banner generation task in a feed entry.

    Expected entry structure:
    - title: Post title for banner generation
    - summary: Post summary (optional)
    - internal_metadata.slug: Post slug (optional)
    - internal_metadata.language: Language code (default: pt-BR)
    """

    def __init__(self, entry: Entry):
        self.entry = entry
        self.title = entry.title
        self.summary = entry.summary or ""
        self.slug = entry.internal_metadata.get("slug") if entry.internal_metadata else None
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
    """Result of processing a single banner task."""

    def __init__(
        self,
        task_entry: Entry,
        document: Document | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ):
        self.task_entry = task_entry
        self.document = document
        self.error = error
        self.error_code = error_code
        self.success = document is not None and error is None


class FeedBannerGenerator:
    """Generates banners from a feed of tasks.

    This class implements the v3 banner generation pipeline:
    1. Accepts a Feed where each Entry is a banner generation task
    2. Processes each task (sequentially or in batch)
    3. Returns a Feed where each Entry is a MEDIA document with the generated banner

    Example:
        generator = FeedBannerGenerator()
        task_feed = Feed(
            id="urn:tasks:banner:batch1",
            title="Banner Generation Tasks",
            updated=datetime.now(UTC),
            entries=[
                Entry(
                    id="task:1",
                    title="Amazing Blog Post",
                    summary="This is about AI...",
                    updated=datetime.now(UTC),
                    internal_metadata={"slug": "amazing-post"},
                )
            ],
        )
        result_feed = generator.generate_from_feed(task_feed)
    """

    def __init__(self, provider: ImageGenerationProvider | None = None):
        """Initialize the feed-based banner generator.

        Args:
            provider: Optional image generation provider.
                     If None, uses the default generate_banner() function.
        """
        self.provider = provider

    def generate_from_feed(
        self,
        task_feed: Feed,
        batch_mode: bool = False,
    ) -> Feed:
        """Generate banners from a feed of tasks.

        Args:
            task_feed: Feed containing banner generation tasks
            batch_mode: If True and using GeminiProvider, use batch API

        Returns:
            Feed with MEDIA documents containing generated banners
        """
        results: list[BannerGenerationResult] = []

        if batch_mode and isinstance(self.provider, GeminiImageGenerationProvider):
            results = self._generate_batch(task_feed.entries)
        else:
            results = self._generate_sequential(task_feed.entries)

        # Convert results to feed entries
        output_entries = []
        for result in results:
            if result.success and result.document:
                output_entries.append(result.document)
            else:
                # Create error document
                error_doc = self._create_error_document(result)
                output_entries.append(error_doc)

        # Create output feed
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

            # Use provider if available, otherwise use default generate_banner
            if self.provider:
                result = self._generate_with_provider(task, banner_input)
            else:
                result = self._generate_with_default(task, banner_input)

            results.append(result)

        return results

    def _generate_batch(self, entries: list[Entry]) -> list[BannerGenerationResult]:
        """Generate banners using batch API (for Gemini provider).

        Note: This requires the GeminiImageGenerationProvider with batch support.
        """
        if not isinstance(self.provider, GeminiImageGenerationProvider):
            # Fallback to sequential if not using Gemini
            return self._generate_sequential(entries)

        results = []
        tasks = [BannerTaskEntry(entry) for entry in entries]

        # Prepare batch requests
        requests = [
            ImageGenerationRequest(
                prompt=self._build_prompt(task.to_banner_input()),
                response_modalities=["IMAGE"],
                aspect_ratio="1:1",
            )
            for task in tasks
        ]

        # Process batch (note: current Gemini provider processes one at a time)
        # This is a placeholder for future batch API support
        for task, request in zip(tasks, requests):
            try:
                batch_result = self.provider.generate(request)
                if batch_result.has_image and batch_result.image_bytes:
                    document = self._create_media_document(
                        task.entry,
                        batch_result.image_bytes,
                        batch_result.mime_type or "image/png",
                    )
                    results.append(
                        BannerGenerationResult(task.entry, document=document)
                    )
                else:
                    results.append(
                        BannerGenerationResult(
                            task.entry,
                            error=batch_result.error or "Unknown error",
                            error_code=batch_result.error_code or "GENERATION_FAILED",
                        )
                    )
            except Exception as e:
                results.append(
                    BannerGenerationResult(
                        task.entry,
                        error=str(e),
                        error_code="GENERATION_EXCEPTION",
                    )
                )

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

        try:
            result = self.provider.generate(request)
            if result.has_image and result.image_bytes:
                document = self._create_media_document(
                    task.entry,
                    result.image_bytes,
                    result.mime_type or "image/png",
                )
                return BannerGenerationResult(task.entry, document=document)
            else:
                return BannerGenerationResult(
                    task.entry,
                    error=result.error or "Unknown error",
                    error_code=result.error_code or "GENERATION_FAILED",
                )
        except Exception as e:
            return BannerGenerationResult(
                task.entry,
                error=str(e),
                error_code="GENERATION_EXCEPTION",
            )

    def _generate_with_default(
        self, task: BannerTaskEntry, banner_input: BannerInput
    ) -> BannerGenerationResult:
        """Generate banner using the default generate_banner function."""
        result = generate_banner(**banner_input.model_dump())

        if result.document:
            # Link to original task
            if result.document.internal_metadata is None:
                result.document.internal_metadata = {}
            result.document.internal_metadata["task_id"] = task.entry.id

            return BannerGenerationResult(task.entry, document=result.document)
        else:
            return BannerGenerationResult(
                task.entry,
                error=result.error or "Unknown error",
                error_code=result.error_code or "GENERATION_FAILED",
            )

    def _build_prompt(self, banner_input: BannerInput) -> str:
        """Build the prompt for banner generation.

        This uses the same logic as the existing generate_banner function.
        """
        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path

        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        env = Environment(loader=FileSystemLoader(prompts_dir))
        template = env.get_template("banner.jinja")

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

        doc = Document.create(
            doc_type=DocumentType.MEDIA,
            title=f"Banner: {task_entry.title}",
            content=image_data.decode("utf-8") if isinstance(image_data, bytes) else image_data,
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
