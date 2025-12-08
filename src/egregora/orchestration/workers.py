"""Background workers for asynchronous task processing.

This module implements the consumer side of the async event-driven architecture.
Workers fetch tasks from the TaskStore, process them, and update their status.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from pydantic_ai import Agent

from egregora.agents.banner.agent import generate_banner
from egregora.agents.enricher import _create_enrichment_row, _normalize_slug
from egregora.data_primitives.document import Document, DocumentType
from egregora.models.google_batch import GoogleBatchModel
from egregora.orchestration.persistence import persist_banner_document, persist_profile_document
from egregora.resources.prompts import render_prompt
from egregora.utils.model_fallback import create_fallback_model

if TYPE_CHECKING:
    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Abstract base class for background workers."""

    def __init__(self, ctx: PipelineContext) -> None:
        self.ctx = ctx
        if not hasattr(ctx, "task_store") or not ctx.task_store:
            msg = "TaskStore not found in PipelineContext; it must be initialized and injected."
            raise ValueError(msg)
        self.task_store = ctx.task_store

    @abstractmethod
    def run(self) -> int:
        """Process pending tasks. Returns number of tasks processed."""


class BannerWorker(BaseWorker):
    """Worker that generates banner images."""

    def run(self) -> int:
        tasks = self.task_store.fetch_pending(task_type="generate_banner")
        if not tasks:
            return 0

        logger.info("Processing %d banner generation tasks", len(tasks))
        count = 0

        for task in tasks:
            try:
                payload = task["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)

                # Extract args
                post_slug = payload["post_slug"]
                title = payload["title"]
                summary = payload["summary"]
                task.get("run_id")

                logger.info("Generating banner for %s", post_slug)

                # Execute generation (synchronous)
                result = generate_banner(post_title=title, post_summary=summary, slug=post_slug)

                if result.success and result.document:
                    # Persist using shared helper
                    web_path = persist_banner_document(self.ctx.output_format, result.document)

                    self.task_store.mark_completed(task["task_id"])
                    logger.info("Banner generated: %s", web_path)

                else:
                    self.task_store.mark_failed(task["task_id"], result.error or "Unknown error")

                count += 1

            except Exception as e:
                logger.exception("Error processing banner task %s", task["task_id"])
                self.task_store.mark_failed(task["task_id"], str(e))

        return count


class ProfileWorker(BaseWorker):
    """Worker that updates author profiles, with coalescing optimization."""

    def run(self) -> int:
        tasks = self.task_store.fetch_pending(task_type="update_profile", limit=1000)
        if not tasks:
            return 0

        # Group by author_uuid
        # Map: author_uuid -> list of tasks (ordered by creation time, ascending)
        author_tasks: dict[str, list[dict]] = {}
        for task in tasks:
            payload = task["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            # Attach parsed payload for convenience
            task["_parsed_payload"] = payload

            author_uuid = payload["author_uuid"]
            if author_uuid not in author_tasks:
                author_tasks[author_uuid] = []
            author_tasks[author_uuid].append(task)

        processed_count = 0

        for author_uuid, task_list in author_tasks.items():
            # If multiple tasks for same author, only execute the LAST one.
            # Mark others as superseded.

            latest_task = task_list[-1]
            superseded_tasks = task_list[:-1]

            # 1. Mark superseded
            for t in superseded_tasks:
                self.task_store.mark_superseded(
                    t["task_id"], reason=f"Superseded by task {latest_task['task_id']}"
                )
                logger.info("Coalesced profile update for %s (Task %s skipped)", author_uuid, t["task_id"])

            # 2. Execute latest
            try:
                content = latest_task["_parsed_payload"]["content"]

                # Write profile using shared helper
                persist_profile_document(
                    self.ctx.output_format,
                    author_uuid,
                    content,
                    source_window="async_worker",
                )

                self.task_store.mark_completed(latest_task["task_id"])
                logger.info("Updated profile for %s (Task %s)", author_uuid, latest_task["task_id"])
                processed_count += 1

            except Exception as e:
                logger.exception("Error processing profile task %s", latest_task["task_id"])
                self.task_store.mark_failed(latest_task["task_id"], str(e))

        return processed_count


class EnrichmentOutput(BaseModel):
    slug: str
    markdown: str


class EnrichmentWorker(BaseWorker):
    """Worker for media enrichment (e.g. image description)."""

    def run(self) -> int:
        """Process pending enrichment tasks in batches."""
        # Configurable batch size
        batch_size = 50
        tasks = self.task_store.fetch_pending(task_type="enrich_url", limit=batch_size)
        media_tasks = self.task_store.fetch_pending(task_type="enrich_media", limit=batch_size)

        processed_count = 0

        if tasks:
            processed_count += self._process_url_batch(tasks)

        if media_tasks:
            processed_count += self._process_media_batch(media_tasks)

        return processed_count

    def _process_url_batch(self, tasks: list[dict[str, Any]]) -> int:
        # Prepare requests
        tasks_data = []
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None

        for task in tasks:
            try:
                payload = task["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                task["_parsed_payload"] = payload

                url = payload["url"]
                prompt = render_prompt(
                    "enrichment.jinja",
                    mode="url_user",
                    prompts_dir=prompts_dir,
                    sanitized_url=url,
                ).strip()

                tasks_data.append({"task": task, "url": url, "prompt": prompt})
            except Exception as e:
                logger.exception("Failed to prepare URL task %s: %s", task["task_id"], e)
                self.task_store.mark_failed(task["task_id"], f"Preparation failed: {e!s}")

        if not tasks_data:
            return 0

        # Execute enrichment for each URL individually with fallback using ThreadPoolExecutor
        enrichment_concurrency = getattr(self.ctx.config.enrichment, "max_concurrent_enrichments", 5)
        global_concurrency = getattr(self.ctx.config.quota, "concurrency", 1)
        max_concurrent = min(enrichment_concurrency, global_concurrency)

        logger.info(
            "Processing %d enrichment tasks with max concurrency of %d (enrichment limit: %d, global limit: %d)",
            len(tasks_data),
            max_concurrent,
            enrichment_concurrency,
            global_concurrency,
        )

        results = []
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_task = {executor.submit(self._enrich_single_url, td): td for td in tasks_data}
            for future in as_completed(future_to_task):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    task = future_to_task[future]["task"]
                    logger.exception("Enrichment failed for %s: %s", task["task_id"], e)
                    results.append((task, None, str(e)))

        # Process results and create documents
        new_rows = []
        for task, output, error in results:
            if error:
                self.task_store.mark_failed(task["task_id"], error)
                continue

            if not output:
                continue

            try:
                payload = task["_parsed_payload"]
                url = payload["url"]
                slug_value = _normalize_slug(output.slug, url)

                doc = Document(
                    content=output.markdown,
                    type=DocumentType.ENRICHMENT_URL,
                    metadata={
                        "url": url,
                        "slug": slug_value,
                        "nav_exclude": True,
                        "hide": ["navigation"],
                    },
                    id=slug_value,  # Semantic ID
                )

                # V3 Architecture: Use ContentLibrary if available
                if self.ctx.library:
                    self.ctx.library.save(doc)
                else:
                    self.ctx.output_format.persist(doc)

                # Create DB row
                metadata = payload["message_metadata"]
                row = _create_enrichment_row(metadata, "URL", url, doc.document_id)
                if row:
                    new_rows.append(row)

                self.task_store.mark_completed(task["task_id"])
            except Exception as e:
                logger.exception("Failed to persist enrichment for %s: %s", task["task_id"], e)
                self.task_store.mark_failed(task["task_id"], f"Persistence error: {e!s}")

        # Insert rows into DB
        if new_rows:
            try:
                self.ctx.storage.ibis_conn.insert("messages", new_rows)
                logger.info("Inserted %d enrichment rows", len(new_rows))
            except Exception as e:
                logger.exception("Failed to insert enrichment rows: %s", e)

        return len(results)

    def _enrich_single_url(self, task_data: dict) -> tuple[dict, EnrichmentOutput | None, str | None]:
        """Enrich a single URL with fallback support (sync wrapper)."""
        task = task_data["task"]
        url = task_data["url"]
        prompt = task_data["prompt"]

        try:
            # Create agent with fallback
            model = create_fallback_model(self.ctx.config.models.enricher)
            agent = Agent(model=model, output_type=EnrichmentOutput)

            # Use run_sync to execute the async agent synchronously
            result = agent.run_sync(prompt)
            return task, result.output, None
        except Exception as e:
            logger.exception("Failed to enrich URL %s: %s", url, e)
            return task, None, str(e)

    def _process_media_batch(self, tasks: list[dict[str, Any]]) -> int:
        requests = []
        task_map = {}
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None

        for task in tasks:
            try:
                payload = task["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                task["_parsed_payload"] = payload

                filename = payload["filename"]
                media_type = payload["media_type"]
                media_id = payload.get("media_id")

                # Use output adapter to retrieve media file (delegates path resolution to sink)
                try:
                    media_doc = self.ctx.output_format.read_document(DocumentType.MEDIA, media_id)
                    if not media_doc or not media_doc.content:
                        logger.warning("Media file not found for task %s: %s", task["task_id"], media_id)
                        self.task_store.mark_failed(task["task_id"], "Media file not found")
                        continue
                    file_bytes = media_doc.content
                except Exception as e:
                    logger.warning("Failed to load media file for task %s: %s", task["task_id"], e)
                    self.task_store.mark_failed(task["task_id"], f"Failed to load media: {e}")
                    continue
                b64_data = base64.b64encode(file_bytes).decode("utf-8")

                prompt = render_prompt(
                    "enrichment.jinja",
                    mode="media_user",
                    prompts_dir=prompts_dir,
                    sanitized_filename=filename,
                    sanitized_mime=media_type,
                ).strip()

                tag = str(task["task_id"])
                requests.append(
                    {
                        "tag": tag,
                        "contents": [
                            {
                                "parts": [
                                    {"text": prompt},
                                    {"inlineData": {"mimeType": media_type, "data": b64_data}},
                                ]
                            }
                        ],
                        "config": {"response_modalities": ["TEXT"]},
                    }
                )
                task_map[tag] = task

            except Exception as e:
                logger.exception("Failed to prepare media task %s: %s", task["task_id"], e)
                self.task_store.mark_failed(task["task_id"], str(e))

        if not requests:
            return 0

        # Execute batch
        model_name = self.ctx.config.models.enricher_vision
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            msg = "GOOGLE_API_KEY or GEMINI_API_KEY required for media enrichment"
            raise ValueError(msg)
        model = GoogleBatchModel(api_key=api_key, model_name=model_name)

        try:
            # Use asyncio.run to execute the async batch method synchronously
            results = asyncio.run(model.run_batch(requests))
        except Exception as e:
            logger.exception("Media enrichment batch failed: %s", e)
            for t in tasks:
                if t["task_id"] in task_map:
                    self.task_store.mark_failed(t["task_id"], f"Batch failed: {e!s}")
            return 0

        # Process results
        new_rows = []
        for res in results:
            task = task_map.get(res.tag)
            if not task:
                continue

            if res.error:
                self.task_store.mark_failed(task["task_id"], str(res.error))
                continue

            text = self._extract_text(res.response)
            try:
                clean_text = text.strip()
                clean_text = clean_text.removeprefix("```json")
                clean_text = clean_text.removeprefix("```")
                clean_text = clean_text.removesuffix("```")

                data = json.loads(clean_text.strip())
                slug = data.get("slug")
                markdown = data.get("markdown")

                if not slug or not markdown:
                    msg = "Missing slug or markdown"
                    raise ValueError(msg)

                payload = task["_parsed_payload"]
                filename = payload["filename"]
                media_type = payload["media_type"]
                media_id = payload.get("media_id")  # Original UUID

                slug_value = _normalize_slug(slug, filename)

                # 1. Update Media Document to use Semantic ID
                # We try to load the original media doc to update its ID (rename it)
                if media_id:
                    try:
                        # Try to load existing media doc
                        # Note: We use payload['media_id'] which was the UUID
                        # MkDocsAdapter might not support finding by UUID if it only indexed paths?
                        # But let's assume get() works or we can reconstruct it.
                        # If get(MEDIA, media_id) fails, we might skip renaming or try path.

                        # Actually, we don't strictly need to load it if we have content.
                        # But we want to RENAME the existing file on disk if it exists.
                        # OutputAdapter.persist handles rename if we pass the NEW doc with NEW ID.
                        # But we need the content.

                        media_doc = self.ctx.output_format.get(DocumentType.MEDIA, media_id)
                        if media_doc:
                            # Update with new semantic ID
                            new_media_doc = media_doc.with_metadata(slug=slug_value)
                            # Force new ID (Semantic)
                            # The Document dataclass computes ID from slug if type is MEDIA.
                            # So just persisting it should trigger the rename in adapter.
                            if self.ctx.library:
                                self.ctx.library.save(new_media_doc)
                            else:
                                self.ctx.output_format.persist(new_media_doc)

                            logger.info("Renamed media %s -> %s", media_id, new_media_doc.document_id)
                    except Exception as e:
                        logger.warning("Failed to rename media document %s: %s", media_id, e)

                # 2. Persist Enrichment Document
                enrichment_metadata = {
                    "filename": filename,
                    "media_type": media_type,
                    "parent_path": payload.get("suggested_path"),
                    "slug": slug_value,
                    "nav_exclude": True,
                    "hide": ["navigation"],
                }

                doc = Document(
                    content=markdown,
                    type=DocumentType.ENRICHMENT_MEDIA,
                    metadata=enrichment_metadata,
                    id=slug_value,  # Explicitly match media ID if possible, or just use slug
                    parent_id=slug_value,  # Link to the (now renamed) media
                )

                # V3 Architecture: Use ContentLibrary
                if self.ctx.library:
                    self.ctx.library.save(doc)
                else:
                    self.ctx.output_format.persist(doc)

                # Create DB row
                metadata = payload["message_metadata"]
                row = _create_enrichment_row(metadata, "Media", filename, doc.document_id)
                if row:
                    new_rows.append(row)

                self.task_store.mark_completed(task["task_id"])

            except Exception as e:
                logger.exception("Failed to parse media result %s: %s", task["task_id"], e)
                self.task_store.mark_failed(task["task_id"], f"Parse error: {e!s}")

        if new_rows:
            try:
                self.ctx.storage.ibis_conn.insert("messages", new_rows)
                logger.info("Inserted %d media enrichment rows", len(new_rows))
            except Exception as e:
                logger.exception("Failed to insert media enrichment rows: %s", e)

        return len(results)

    def _extract_text(self, response: dict[str, Any] | None) -> str:
        if not response:
            return ""
        if "text" in response:
            return response["text"]
        texts = []
        for cand in response.get("candidates") or []:
            content = cand.get("content") or {}
            for part in content.get("parts") or []:
                if "text" in part:
                    texts.append(part["text"])
        return "\n".join(texts)
