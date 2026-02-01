"""URL Enrichment logic."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import ibis
from google import genai
from google.genai import types
from pydantic_ai import Agent, WebFetchTool

from egregora.agents.enricher.helpers import (
    HEARTBEAT_INTERVAL,
    create_enrichment_row,
    fetch_url_with_jina,
    normalize_slug,
    uuid_to_str,
)
from egregora.agents.enricher.types import EnrichmentOutput
from egregora.agents.exceptions import (
    EnrichmentExecutionError,
    EnrichmentParsingError,
)
from egregora.data_primitives.document import Document, DocumentType
from egregora.database.message_repository import MessageRepository
from egregora.llm.api_keys import get_google_api_key
from egregora.orchestration.cache import make_enrichment_cache_key
from egregora.orchestration.exceptions import CacheKeyNotFoundError
from egregora.resources.prompts import render_prompt

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.agents.enricher.types import EnrichmentRuntimeContext
    from egregora.agents.enricher.worker import EnrichmentWorker

logger = logging.getLogger(__name__)


class UrlEnrichmentHandler:
    """Handler for URL enrichment tasks."""

    def __init__(self, worker: EnrichmentWorker | None) -> None:
        self.worker = worker
        if worker:
            self.ctx = worker.ctx
            self.task_store = getattr(worker, "task_store", None)
        else:
            self.ctx = None
            self.task_store = None

    def enqueue(
        self,
        messages_table: Table,
        max_enrichments: int,
        context: EnrichmentRuntimeContext,
        run_id: uuid.UUID,
        *,
        enable_url: bool,
    ) -> int:
        """Enqueue URL enrichment tasks."""
        if not enable_url or max_enrichments <= 0:
            return 0

        backend = context.duckdb_connection or messages_table._find_backend(use_default=True)
        repo = MessageRepository(backend)
        candidates = repo.get_url_enrichment_candidates(messages_table, max_enrichments)

        # Pre-check database for already enriched URLs to avoid redundant tasks
        urls_to_check = [c[0] for c in candidates]
        existing_urls: set[str] = set()
        if urls_to_check:
            try:
                # Check for existing URL enrichments in the messages table
                db_existing = (
                    messages_table.filter(
                        (messages_table.media_type == "URL") & (messages_table.media_url.isin(urls_to_check))
                    )
                    .select("media_url")
                    .execute()
                )
                existing_urls = set(db_existing["media_url"].tolist())
            except (Exception, ValueError) as exc:  # IbisError is dynamic, check imports
                logger.warning(
                    "Failed to check database for existing URL enrichments; falling back to cache only: %s",
                    exc,
                )

        scheduled = 0
        tasks_batch = []
        for url, metadata in candidates:
            # Skip if already in database OR disk cache
            if url in existing_urls:
                continue

            cache_key = make_enrichment_cache_key(kind="url", identifier=url)
            try:
                context.cache.load(cache_key)
                continue
            except CacheKeyNotFoundError:
                pass

            payload = {
                "type": "url",
                "url": url,
                "message_metadata": self._serialize_metadata(metadata),
            }
            if context.task_store:
                tasks_batch.append(("enrich_url", payload))
                scheduled += 1

        if context.task_store and tasks_batch:
            context.task_store.enqueue_batch(tasks_batch)

        return scheduled

    def process_batch(self, tasks: list[dict[str, Any]]) -> int:
        """Process a batch of URL enrichment tasks."""
        tasks_data = self._prepare_tasks(tasks)
        if not tasks_data:
            return 0

        max_concurrent = self.worker.determine_concurrency(len(tasks_data))
        results = self._execute_enrichments(tasks_data, max_concurrent)
        return self._persist_results(results)

    def _prepare_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Parse payloads and render prompts for URL enrichment tasks."""
        tasks_data: list[dict[str, Any]] = []
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
                msg = f"Failed to prepare URL task {task.get('task_id')}: {e}"
                logger.exception(msg)
                if self.task_store:
                    self.task_store.mark_failed(task.get("task_id"), msg)

        return tasks_data

    def _execute_enrichments(
        self, tasks_data: list[dict[str, Any]], max_concurrent: int
    ) -> list[tuple[dict, EnrichmentOutput | None, str | None]]:
        """Execute URL enrichments based on configured strategy."""
        strategy = getattr(self.worker.enrichment_config, "strategy", "individual")
        total = len(tasks_data)

        # Use single-call batch for batch_all strategy with multiple URLs
        if strategy == "batch_all" and total > 1:
            try:
                logger.info("[URLEnricher] Using single-call batch mode for %d URLs", total)
                return self._execute_single_call(tasks_data)
            except Exception as single_call_exc:
                logger.warning(
                    "[URLEnricher] Single-call batch failed (%s), falling back to individual",
                    single_call_exc,
                )

        # Individual calls (default fallback)
        return self._execute_individual(tasks_data, max_concurrent)

    def _execute_individual(
        self, tasks_data: list[dict[str, Any]], max_concurrent: int
    ) -> list[tuple[dict, EnrichmentOutput | None, str | None]]:
        """Execute URL enrichments individually with model rotation."""
        results: list[tuple[dict, EnrichmentOutput | None, str | None]] = []
        total = len(tasks_data)
        last_log_time = time.time()

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_task = {executor.submit(self._enrich_single_url, td): td for td in tasks_data}
            for i, future in enumerate(as_completed(future_to_task), 1):
                try:
                    results.append(future.result())

                    # Heartbeat logging
                    if time.time() - last_log_time > HEARTBEAT_INTERVAL:
                        logger.info("[Heartbeat] URL Enrichment: %d/%d (%.1f%%)", i, total, (i / total) * 100)
                        last_log_time = time.time()

                except EnrichmentExecutionError as exc:
                    task = future_to_task[future]["task"]
                    logger.error(
                        "Enrichment execution failed for %s: %s", task["task_id"], exc, exc_info=True
                    )
                    results.append((task, None, str(exc)))
                except Exception as exc:
                    task = future_to_task[future]["task"]
                    logger.exception("Unexpected error during enrichment for %s", task["task_id"])
                    results.append((task, None, str(exc)))

        logger.info("[Enrichment] URL tasks complete: %d/%d", len(results), total)
        return results

    def _enrich_single_url(self, task_data: dict) -> tuple[dict, EnrichmentOutput | None, str | None]:
        """Enrich a single URL with fallback support (sync wrapper)."""
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        task = task_data["task"]
        url = task_data["url"]
        prompt = task_data["prompt"]

        try:
            # Create agent with fallback
            model_name = self.ctx.config.models.enricher
            provider = GoogleProvider(api_key=get_google_api_key())
            model = GoogleModel(
                model_name.removeprefix("google-gla:"),
                provider=provider,
            )

            # REGISTER TOOLS:
            # 1. WebFetchTool: Standard client-side fetcher (primary) - passed via builtin_tools
            # 2. fetch_url_with_jina: Fallback service for difficult pages - passed via tools
            agent = Agent(
                model=model,
                output_type=EnrichmentOutput,
                builtin_tools=[WebFetchTool()],  # Built-in tools must use builtin_tools param
                tools=[fetch_url_with_jina],  # Custom tools use regular tools param
            )

            # Since this is running in a thread pool, create a new event loop.
            async def _run_async() -> Any:
                return await agent.run(prompt)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_run_async())
            finally:
                loop.close()

        except Exception as e:
            msg = f"Failed to enrich URL {url}: {e}"
            raise EnrichmentExecutionError(msg) from e
        else:
            return task, result.output, None

    def _execute_single_call(
        self, tasks_data: list[dict[str, Any]]
    ) -> list[tuple[dict, EnrichmentOutput | None, str | None]]:
        """Execute all URL enrichments in a single API call."""
        # Note: logic copied from original EnrichmentWorker._execute_url_single_call
        api_key = get_google_api_key()

        # Extract URLs from tasks
        urls = []
        for td in tasks_data:
            task = td["task"]
            payload = task.get("_parsed_payload") or json.loads(task.get("payload", "{}"))
            url = payload.get("url", "")
            urls.append(url)

        # Render prompt from Jinja template
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None
        combined_prompt = render_prompt(
            "enrichment.jinja",
            mode="url_batch",
            prompts_dir=prompts_dir,
            url_count=len(urls),
            urls_json=json.dumps(urls),
            pii_prevention=getattr(self.ctx.config.privacy, "pii_prevention", None),
        ).strip()

        # Use initialized rotator if available
        if self.worker.rotator:

            def call_with_model_and_key(model: str, api_key: str) -> str:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model,
                    contents=cast("Any", [{"parts": [{"text": combined_prompt}]}]),
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                return response.text or ""

            response_text = self.worker.rotator.call_with_rotation(call_with_model_and_key)
        else:
            # No rotation - use configured model and API key
            model_name = self.ctx.config.models.enricher
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=cast("Any", [{"parts": [{"text": combined_prompt}]}]),
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            response_text = response.text or ""

        logger.debug(
            "[URLEnricher] Single-call response received (length: %d)",
            len(response_text) if response_text else 0,
        )

        # Parse JSON response
        try:
            results_dict = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning("[URLEnricher] Failed to parse JSON response: %s", e)
            msg = f"Failed to parse batch response: {e}"
            raise EnrichmentParsingError(msg) from e

        # Convert to result tuples
        results: list[tuple[dict, EnrichmentOutput | None, str | None]] = []
        for td in tasks_data:
            task = td["task"]
            payload = task.get("_parsed_payload") or json.loads(task.get("payload", "{}"))
            url = payload.get("url", "")

            enrichment = results_dict.get(url, {})
            if enrichment:
                # Build EnrichmentOutput from result
                slug = enrichment.get("slug", "")
                title = enrichment.get("title") or slug.replace("-", " ").title()
                tags = enrichment.get("tags", [])
                summary = enrichment.get("summary", "")
                takeaways = enrichment.get("key_takeaways", [])

                # Build markdown from enrichment data
                takeaways_md = "\n".join(f"- {t}" for t in takeaways) if takeaways else ""
                markdown = f"""# {slug}

## Summary
{summary}

## Key Takeaways
{takeaways_md}

---
*Source: [{url}]({url})*
"""
                output = EnrichmentOutput(slug=slug, markdown=markdown, title=title, tags=tags)
                results.append((task, output, None))
                logger.info("[URLEnricher] Processed %s via single-call batch", url)
            else:
                results.append((task, None, f"No result for {url}"))

        logger.info("[URLEnricher] Single-call batch complete: %d/%d", len(results), len(tasks_data))
        return results

    def _persist_results(self, results: list[tuple[dict, EnrichmentOutput | None, str | None]]) -> int:
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
                slug_value = normalize_slug(output.slug, url)

                doc = Document(
                    content=output.markdown,
                    type=DocumentType.ENRICHMENT_URL,
                    metadata={
                        "url": url,
                        "slug": slug_value,
                        "title": output.title or slug_value.replace("-", " ").title(),
                        "tags": output.tags or [],
                        "date": datetime.now(UTC).isoformat(),
                        "nav_exclude": True,
                        "hide": ["navigation"],
                    },
                    id=slug_value,  # Semantic ID
                )

                # Main Architecture: Use ContentLibrary if available
                if self.ctx.library:
                    cast("Any", self.ctx.library).save(doc)
                elif self.ctx.output_sink:
                    self.ctx.output_sink.persist(doc)

                metadata = payload["message_metadata"]
                row = create_enrichment_row(metadata, "URL", url, doc.document_id, media_identifier=url)
                if row:
                    new_rows.append(row)

                self.task_store.mark_completed(task["task_id"])
            except Exception as exc:
                logger.exception("Failed to persist enrichment for %s", task["task_id"])
                self.task_store.mark_failed(task["task_id"], f"Persistence error: {exc!s}")

        if new_rows:
            try:
                t = ibis.memtable(new_rows)
                self.ctx.storage.write_table(t, "messages", mode="append")
                logger.info("Inserted %d enrichment rows", len(new_rows))
            except Exception:
                logger.exception("Failed to insert enrichment rows")

        return len(results)

    def _serialize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        timestamp = metadata.get("ts")
        created_at = metadata.get("created_at")
        return {
            "ts": timestamp.isoformat() if timestamp else None,
            "tenant_id": metadata.get("tenant_id"),
            "source": metadata.get("source"),
            "thread_id": uuid_to_str(metadata.get("thread_id")),
            "author_uuid": uuid_to_str(metadata.get("author_uuid")),
            "created_at": (
                created_at.isoformat() if created_at and hasattr(created_at, "isoformat") else created_at
            ),
            "created_by_run": uuid_to_str(metadata.get("created_by_run")),
        }
