"""Background workers for asynchronous task processing.

This module implements the consumer side of the async event-driven architecture.
Workers fetch tasks from the TaskStore, process them, and update their status.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from egregora.agents.banner.agent import generate_banner
from egregora.orchestration.persistence import persist_banner_document, persist_profile_document

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

                # Execute generation (synchronous for now, but in worker thread/process conceptually)
                result = generate_banner(post_title=title, post_summary=summary, slug=post_slug)

                if result.success and result.document:
                    # Persist using shared helper
                    web_path = persist_banner_document(self.ctx.output_format, result.document)

                    self.task_store.mark_completed(task["task_id"])
                    logger.info("Banner generated: %s", web_path)

                    # TODO: Enqueue 'enrich_media' task here if we implement chaining

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


class EnrichmentWorker(BaseWorker):
    """Worker for media enrichment (e.g. image description)."""

    def run(self) -> int:
        """Process pending enrichment tasks in batches."""
        # Configurable batch size
        batch_size = 50
        tasks = self.task_store.fetch_pending(task_type="enrich_url", limit=batch_size)
        media_tasks = self.task_store.fetch_pending(task_type="enrich_media", limit=batch_size)

        # Combine tasks but process separately or together?
        # GoogleBatchModel can handle mixed requests if we structure them right.
        # But let's process them in separate batches for simplicity of result handling.

        processed_count = 0

        if tasks:
            processed_count += self._process_url_batch(tasks)

        if media_tasks:
            processed_count += self._process_media_batch(media_tasks)

        return processed_count

    def _process_url_batch(self, tasks: list[dict[str, Any]]) -> int:
        from egregora.agents.enricher import _create_enrichment_row, _normalize_slug
        from egregora.data_primitives.document import Document, DocumentType
        from egregora.resources.prompts import render_prompt

        # Prepare requests
        requests = []
        task_map = {}

        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None

        for task in tasks:
            payload = task["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            task["_parsed_payload"] = payload

            url = payload["url"]

            # Render prompt
            prompt = render_prompt(
                "enrichment.jinja",
                mode="url_user",
                prompts_dir=prompts_dir,
                sanitized_url=url,  # Assuming sanitized in schedule? No, should sanitize here.
                # For simplicity, passing raw url, template should handle or we add helper
            ).strip()

            tag = str(task["task_id"])
            requests.append(
                {
                    "tag": tag,
                    "contents": [{"parts": [{"text": prompt}]}],
                    "config": {"response_modalities": ["TEXT"]},
                }
            )
            task_map[tag] = task

        if not requests:
            return 0

        # Execute enrichment for each URL individually with fallback
        import asyncio

        from pydantic import BaseModel
        from pydantic_ai import Agent

        from egregora.utils.model_fallback import create_fallback_model

        class EnrichmentOutput(BaseModel):
            slug: str
            markdown: str

        async def enrich_single_url(task_data: dict) -> tuple[dict, EnrichmentOutput | None, str | None]:
            """Enrich a single URL with fallback support."""
            task = task_data["task"]
            url = task_data["url"]
            prompt = task_data["prompt"]

            try:
                # Create agent with fallback
                model = create_fallback_model(self.ctx.config.models.enricher)
                agent = Agent(model=model, output_type=EnrichmentOutput)
                result = await agent.run(prompt)
                # With output_type, result IS the EnrichmentOutput
                return task, result, None
            except Exception as e:
                logger.error("Failed to enrich URL %s: %s", url, e)
                return task, None, str(e)

        async def process_all_urls():
            # Prepare all task data
            tasks_data = []
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
                    logger.error("Failed to prepare URL task %s: %s", task["task_id"], e)
                    self.task_store.mark_failed(task["task_id"], f"Preparation failed: {e!s}")

            # Process all tasks with controlled concurrency
            # This prevents hitting rate limits
            max_concurrent = getattr(self.ctx.config.enrichment, "max_concurrent_enrichments", 5)
            semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(
                "Processing %d enrichment tasks with max concurrency of %d", len(tasks_data), max_concurrent
            )

            async def process_with_semaphore(task_data):
                async with semaphore:
                    return await enrich_single_url(task_data)

            results = await asyncio.gather(
                *[process_with_semaphore(td) for td in tasks_data], return_exceptions=True
            )

            # Handle any exceptions from gather
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task = tasks_data[i]["task"]
                    logger.error("Enrichment failed for %s: %s", task["task_id"], result)
                    processed_results.append((task, None, str(result)))
                else:
                    processed_results.append(result)

            return processed_results

        try:
            results = asyncio.run(process_all_urls())
        except Exception as e:
            logger.error("Enrichment processing failed: %s", e)
            for t in tasks:
                self.task_store.mark_failed(t["task_id"], f"Processing failed: {e!s}")
            return 0

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
                )
                self.ctx.output_format.persist(doc)

                # Create DB row
                metadata = payload["message_metadata"]
                row = _create_enrichment_row(metadata, "URL", url, doc.document_id)
                if row:
                    new_rows.append(row)

                self.task_store.mark_completed(task["task_id"])
            except Exception as e:
                logger.error("Failed to persist enrichment for %s: %s", task["task_id"], e)
                self.task_store.mark_failed(task["task_id"], f"Persistence error: {e!s}")

        # Insert rows into DB
        if new_rows:
            # We need to append to the messages table or enrichment table?
            # The original logic combined rows into messages table.
            # But messages table is usually read-only from source?
            # No, it's an Ibis table.
            # We should probably insert into a dedicated 'enrichments' table and view union them?
            # Or insert back into 'messages' if it's mutable?
            # DuckDB tables are mutable.
            # IR_MESSAGE_SCHEMA matches.

            # We can use the storage manager to insert.
            try:
                self.ctx.storage.ibis_conn.insert("messages", new_rows)
                logger.info("Inserted %d enrichment rows", len(new_rows))
            except Exception as e:
                logger.error("Failed to insert enrichment rows: %s", e)

        return len(results)

    def _process_media_batch(self, tasks: list[dict[str, Any]]) -> int:
        import base64

        from egregora.agents.enricher import _create_enrichment_row, _normalize_slug
        from egregora.data_primitives.document import Document, DocumentType
        from egregora.resources.prompts import render_prompt

        requests = []
        task_map = {}
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None

        for task in tasks:
            payload = task["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            task["_parsed_payload"] = payload

            filename = payload["filename"]
            media_type = payload["media_type"]
            suggested_path = payload.get("suggested_path")

            # Load binary content
            # We assume suggested_path is valid and accessible
            # If not, we might fail.
            # suggested_path is relative to output dir usually?
            # Document.suggested_path is usually relative.
            # We need to resolve it against output_dir.

            file_path = None
            if suggested_path:
                # Try resolving against media_dir
                # self.ctx.media_dir is where media is saved
                # But suggested_path might be 'media/foo.jpg'
                full_path = self.ctx.output_dir / suggested_path
                if full_path.exists():
                    file_path = full_path

            if not file_path or not file_path.exists():
                logger.warning("Media file not found for task %s: %s", task["task_id"], suggested_path)
                self.task_store.mark_failed(task["task_id"], "Media file not found")
                continue

            try:
                file_bytes = file_path.read_bytes()
                # Encode base64 for batch request (inline data)
                # Or use blob upload?
                # GoogleBatchModel _to_genai_contents handles base64 encoding if passed as 'data'
                # But here we are constructing request dict manually for run_batch.
                # run_batch expects 'contents' -> 'parts'

                # We can pass base64 string in 'inlineData'
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
                logger.error("Failed to prepare media task %s: %s", task["task_id"], e)
                self.task_store.mark_failed(task["task_id"], str(e))

        if not requests:
            return 0

        # Execute batch
        model_name = self.ctx.config.models.enricher_vision
        import asyncio

        from egregora.config.settings import get_google_api_key
        from egregora.models.google_batch import GoogleBatchModel

        model = GoogleBatchModel(api_key=get_google_api_key(), model_name=model_name)

        try:
            results = asyncio.run(model.run_batch(requests))
        except Exception as e:
            logger.error("Media enrichment batch failed: %s", e)
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
                    raise ValueError("Missing slug or markdown")

                payload = task["_parsed_payload"]
                filename = payload["filename"]
                media_type = payload["media_type"]
                url = payload.get("url")  # Might not be present for media

                slug_value = _normalize_slug(slug, filename)

                # Create Enriched Media Document
                # We need to link it to the original media doc?
                # The original media doc is already persisted.
                # We create a new enrichment doc.

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
                )
                self.ctx.output_format.persist(doc)

                # Create DB row
                metadata = payload["message_metadata"]
                row = _create_enrichment_row(metadata, "Media", filename, doc.document_id)
                if row:
                    new_rows.append(row)

                self.task_store.mark_completed(task["task_id"])

            except Exception as e:
                logger.error("Failed to parse media result %s: %s", task["task_id"], e)
                self.task_store.mark_failed(task["task_id"], f"Parse error: {e!s}")

        if new_rows:
            try:
                self.ctx.storage.ibis_conn.insert("messages", new_rows)
                logger.info("Inserted %d media enrichment rows", len(new_rows))
            except Exception as e:
                logger.error("Failed to insert media enrichment rows: %s", e)

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
