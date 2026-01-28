"""Batch banner processor for asynchronous workers.

This module keeps the V2 pipeline independent from the Pure feed-based plan by
operating on simple task payloads that mirror what the TaskStore enqueues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from egregora.agents.banner.agent import BannerInput, generate_banner
from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
)
from egregora.data_primitives.document import Document, DocumentType

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(slots=True)
class BannerTaskEntry:
    """Task payload parsed from the TaskStore queue."""

    task_id: str
    title: str
    summary: str
    slug: str | None = None
    language: str = "pt-BR"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_banner_input(self) -> BannerInput:
        """Convert the stored payload into the synchronous BannerInput."""
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
        task: BannerTaskEntry,
        document: Document | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.task = task
        self.document = document
        self.error = error
        self.error_code = error_code

    @property
    def success(self) -> bool:
        """Return True when a banner document was produced."""
        return self.document is not None and self.error is None


class BannerBatchProcessor:
    """Process queued banner tasks sequentially or via Gemini batch provider."""

    def __init__(
        self,
        provider: ImageGenerationProvider | None = None,
        prompts_dir: Path | None = None,
    ) -> None:
        self.provider = provider

        if prompts_dir is None:
            prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        self.jinja_env = Environment(
            loader=FileSystemLoader(prompts_dir),
            autoescape=select_autoescape(enabled_extensions=("jinja", "jinja2", "html", "xml")),
        )

    def process_tasks(
        self,
        tasks: Iterable[BannerTaskEntry],
        *,
        batch_mode: bool = False,
    ) -> list[BannerGenerationResult]:
        """Process scheduled banner tasks."""
        task_list = list(tasks)
        if not task_list:
            return []

        if batch_mode and isinstance(self.provider, GeminiImageGenerationProvider):
            return self._generate_batch(task_list)

        return self._generate_sequential(task_list)

    def _generate_sequential(self, tasks: list[BannerTaskEntry]) -> list[BannerGenerationResult]:
        results: list[BannerGenerationResult] = []

        for task in tasks:
            banner_input = task.to_banner_input()

            if self.provider:
                result = self._generate_with_provider(task, banner_input)
            else:
                result = self._generate_with_default(task, banner_input)

            results.append(result)

        return results

    def _generate_batch(self, tasks: list[BannerTaskEntry]) -> list[BannerGenerationResult]:
        if not isinstance(self.provider, GeminiImageGenerationProvider):
            return self._generate_sequential(tasks)

        results: list[BannerGenerationResult] = []
        requests = [
            ImageGenerationRequest(
                prompt=self._build_prompt(task.to_banner_input()),
                response_modalities=["IMAGE"],
                aspect_ratio="1:1",
            )
            for task in tasks
        ]

        for task, request in zip(tasks, requests, strict=True):
            try:
                batch_result = self.provider.generate(request)
                if batch_result.has_image and batch_result.image_bytes:
                    document = self._create_document(
                        task,
                        batch_result.image_bytes,
                        batch_result.mime_type or "image/png",
                        extra_metadata={"language": task.language},
                    )
                    results.append(BannerGenerationResult(task, document=document))
                else:
                    results.append(
                        BannerGenerationResult(
                            task,
                            error=batch_result.error or "Unknown error",
                            error_code=batch_result.error_code or "GENERATION_FAILED",
                        )
                    )
            except (RuntimeError, ValueError) as exc:
                results.append(
                    BannerGenerationResult(
                        task,
                        error=str(exc),
                        error_code="GENERATION_EXCEPTION",
                    )
                )

        return results

    def _generate_with_provider(
        self, task: BannerTaskEntry, banner_input: BannerInput
    ) -> BannerGenerationResult:
        request = ImageGenerationRequest(
            prompt=self._build_prompt(banner_input),
            response_modalities=["IMAGE"],
            aspect_ratio="1:1",
        )

        try:
            result = self.provider.generate(request) if self.provider else None
            if result and result.has_image and result.image_bytes:
                document = self._create_document(
                    task,
                    result.image_bytes,
                    result.mime_type or "image/png",
                    extra_metadata={"language": task.language},
                )
                return BannerGenerationResult(task, document=document)
            error = result.error if result else "Unknown error"
            error_code = (result.error_code if result else None) or "GENERATION_FAILED"
            return BannerGenerationResult(task, error=error, error_code=error_code)
        except (RuntimeError, ValueError) as exc:
            return BannerGenerationResult(task, error=str(exc), error_code="GENERATION_EXCEPTION")

    def _generate_with_default(
        self, task: BannerTaskEntry, banner_input: BannerInput
    ) -> BannerGenerationResult:
        result = generate_banner(**banner_input.model_dump())

        if result.document:
            document = self._attach_task_metadata(task, result.document)
            return BannerGenerationResult(task, document=document)
        return BannerGenerationResult(
            task,
            error=result.error or "Unknown error",
            error_code=result.error_code or "GENERATION_FAILED",
        )

    def _build_prompt(self, banner_input: BannerInput) -> str:
        template = self.jinja_env.get_template("banner.jinja")
        return template.render(
            post_title=banner_input.post_title,
            post_summary=banner_input.post_summary,
        )

    def _create_document(
        self,
        task: BannerTaskEntry,
        image_data: bytes,
        mime_type: str,
        *,
        extra_metadata: dict[str, Any] | None = None,
    ) -> Document:
        metadata = self._build_metadata(task, extra_metadata)
        metadata["mime_type"] = mime_type
        metadata["generated_at"] = datetime.now(UTC).isoformat()

        return Document(
            content=image_data,
            type=DocumentType.MEDIA,
            metadata=metadata,
        )

    def _attach_task_metadata(self, task: BannerTaskEntry, document: Document) -> Document:
        updates: dict[str, Any] = {}
        if document.metadata is None:
            # Should not happen with default_factory but for safety
            updates = {}
        else:
            updates = document.metadata.copy()

        updates.setdefault("slug", task.slug)
        updates.setdefault("language", task.language)
        updates.setdefault("task_id", task.task_id)
        updates.setdefault("generated_at", datetime.now(UTC).isoformat())

        return document.with_metadata(**updates)

    def _build_metadata(
        self,
        task: BannerTaskEntry,
        extra_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        metadata = {"task_id": task.task_id}
        if task.slug:
            metadata["slug"] = task.slug
        if task.language:
            metadata["language"] = task.language
        if task.metadata:
            metadata.update(task.metadata)
        if extra_metadata:
            metadata.update(extra_metadata)
        return metadata
