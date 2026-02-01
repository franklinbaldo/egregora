"""Media Enrichment logic."""

from __future__ import annotations

import base64
import json
import logging
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import duckdb
import ibis
from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import types
from ibis.common.exceptions import IbisError
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

from egregora.agents.enricher.helpers import (
    create_enrichment_row,
    normalize_slug,
    uuid_to_str,
)
from egregora.agents.enricher.types import (
    EnrichmentOutput,
    MediaEnrichmentConfig,
)
from egregora.agents.exceptions import (
    EnrichmentParsingError,
    EnrichmentSlugError,
    MediaStagingError,
)
from egregora.data_primitives.document import Document, DocumentType
from egregora.database.message_repository import MessageRepository
from egregora.llm.api_keys import get_google_api_key
from egregora.llm.providers.google_batch import GoogleBatchModel
from egregora.orchestration.cache import make_enrichment_cache_key
from egregora.orchestration.exceptions import CacheKeyNotFoundError
from egregora.resources.prompts import render_prompt

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.agents.enricher.types import EnrichmentRuntimeContext
    from egregora.agents.enricher.worker import EnrichmentWorker

logger = logging.getLogger(__name__)


class MediaEnrichmentHandler:
    """Handler for Media enrichment tasks."""

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
        context: EnrichmentRuntimeContext,
        run_id: uuid.UUID,
        config: MediaEnrichmentConfig,
    ) -> int:
        """Enqueue media enrichment tasks."""
        if not config.enable_media or config.max_enrichments <= 0:
            return 0

        backend = context.duckdb_connection or messages_table._find_backend(use_default=True)
        repo = MessageRepository(backend)
        candidates = repo.get_media_enrichment_candidates(
            messages_table, config.media_mapping, config.max_enrichments
        )

        # Pre-check database for already enriched media
        media_ids_to_check = [c[1].document_id for c in candidates]
        existing_media: set[str] = set()
        if media_ids_to_check:
            try:
                db_existing = (
                    messages_table.filter(
                        (messages_table.media_type == "Media")
                        & (messages_table.media_url.isin(media_ids_to_check))
                    )
                    .select("media_url")
                    .execute()
                )
                existing_media = set(db_existing["media_url"].tolist())
            except (Exception, ValueError) as exc:
                logger.warning(
                    "Failed to check database for existing Media enrichments; falling back to cache only: %s",
                    exc,
                )

        scheduled = 0
        tasks_batch = []
        for ref, media_doc, metadata in candidates:
            if media_doc.document_id in existing_media:
                continue

            cache_key = make_enrichment_cache_key(kind="media", identifier=media_doc.document_id)
            try:
                context.cache.load(cache_key)
                continue
            except CacheKeyNotFoundError:
                pass

            payload = {
                "type": "media",
                "ref": ref,
                "media_id": media_doc.document_id,
                "filename": media_doc.metadata.get("filename"),
                "original_filename": media_doc.metadata.get("original_filename"),
                "media_type": media_doc.metadata.get("media_type"),
                "suggested_path": (str(media_doc.suggested_path) if media_doc.suggested_path else None),
                "message_metadata": self._serialize_metadata(metadata),
            }
            if context.task_store:
                tasks_batch.append(("enrich_media", payload))
                scheduled += 1
            if scheduled >= config.max_enrichments:
                break

        if context.task_store and tasks_batch:
            context.task_store.enqueue_batch(tasks_batch)

        return scheduled

    def process_batch(self, tasks: list[dict[str, Any]]) -> int:
        """Process a batch of media enrichment tasks."""
        requests, task_map = self._prepare_requests(tasks)
        if not requests:
            return 0

        results = self._execute_batch(requests, task_map)
        return self._persist_results(results, task_map)

    def _prepare_requests(
        self, tasks: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None
        requests: list[dict[str, Any]] = []
        task_map: dict[str, dict[str, Any]] = {}

        for task in tasks:
            try:
                payload = task["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                task["_parsed_payload"] = payload

                # Stage the file to disk (ephemeral)
                try:
                    staged_path = self._stage_file(task, payload)
                except MediaStagingError as exc:
                    logger.warning("Failed to stage media for task %s: %s", task["task_id"], exc)
                    self.task_store.mark_failed(task["task_id"], str(exc))
                    continue

                # Store staged path in task for later persistence
                task["_staged_path"] = str(staged_path)

                filename = payload["filename"]
                media_type = payload["media_type"]

                media_part = self._prepare_media_content(staged_path, media_type)

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
                                    media_part,
                                ]
                            }
                        ],
                        "config": {},
                    }
                )
                task_map[tag] = task

            except Exception as exc:
                logger.exception("Failed to prepare media task %s", task.get("task_id"))
                self.task_store.mark_failed(task.get("task_id"), str(exc))

        return requests, task_map

    def _stage_file(self, task: dict[str, Any], payload: dict[str, Any]) -> Path:
        """Extract media file from ZIP to ephemeral staging directory."""
        original_filename = payload.get("original_filename") or payload.get("filename")
        if not original_filename:
            msg = "No filename in task payload"
            raise MediaStagingError(msg)

        target_lower = original_filename.lower()

        # Access worker's zip handle
        zf = self.worker.zip_handle
        media_index = self.worker.media_index
        should_close = False

        # Ensure ZIP handle is available, opening it if necessary.
        if zf is None:
            # Try to open it using worker's context
            input_path = self.ctx.input_path
            if not input_path or not input_path.exists():
                msg = f"Input path not available for media task {task['task_id']}"
                raise MediaStagingError(msg)
            try:
                import zipfile

                zf = zipfile.ZipFile(input_path, "r")
                should_close = True
                media_index = {
                    Path(info.filename).name.lower(): info.filename
                    for info in zf.infolist()
                    if not info.is_dir()
                }
            except (OSError, zipfile.BadZipFile) as exc:
                msg = f"Failed to open source ZIP: {exc}"
                raise MediaStagingError(msg) from exc

        try:
            full_path = media_index.get(target_lower)
            if not full_path:
                msg = f"Media file {original_filename} not found in ZIP"
                raise MediaStagingError(msg)

            safe_name = f"{task['task_id']}_{Path(full_path).name}"
            target_path = Path(self.worker.staging_dir.name) / safe_name

            if target_path.exists():
                return target_path

            with zf.open(full_path) as source, target_path.open("wb") as dest:
                shutil.copyfileobj(source, dest)

            self.worker.staged_files.add(str(target_path))
            return target_path
        except Exception as exc:
            msg = f"Failed to stage media file {original_filename}: {exc}"
            raise MediaStagingError(msg) from exc
        finally:
            if should_close and zf:
                zf.close()

    def _prepare_media_content(self, file_path: Path, mime_type: str) -> dict[str, Any]:
        """Prepare media content for API request, using File API for large files."""
        # Threshold: 20 MB
        params = getattr(self.ctx.config.enrichment, "large_file_threshold_mb", 20)
        threshold_bytes = params * 1024 * 1024

        file_size = file_path.stat().st_size

        if file_size > threshold_bytes:
            from google import genai

            logger.info(
                "File %s is %.2f MB (threshold: %d MB), using File API upload",
                file_path.name,
                file_size / (1024 * 1024),
                params,
            )

            api_key = get_google_api_key()
            client = genai.Client(api_key=api_key)

            # Upload file
            uploaded_file = client.files.upload(file=str(file_path), config={"mime_type": mime_type})
            logger.info("Uploaded file %s to %s", file_path.name, uploaded_file.uri)

            return {"fileData": {"mimeType": mime_type, "fileUri": uploaded_file.uri}}
        # Inline base64 for small files
        file_bytes = file_path.read_bytes()
        b64_data = base64.b64encode(file_bytes).decode("utf-8")
        return {
            "inlineData": {
                "mimeType": mime_type,
                "data": b64_data,
            }
        }

    def _execute_batch(
        self, requests: list[dict[str, Any]], task_map: dict[str, dict[str, Any]]
    ) -> list[Any]:
        """Execute media enrichments based on configured strategy."""
        model_name = self.ctx.config.models.enricher_vision
        api_key = get_google_api_key()

        strategy = getattr(self.worker.enrichment_config, "strategy", "individual")
        if strategy == "batch_all" and len(requests) > 1:
            try:
                logger.info("[MediaEnricher] Using single-call batch mode for %d images", len(requests))
                return self._execute_single_call(requests, task_map, model_name, api_key)
            except (google_exceptions.GoogleAPICallError, EnrichmentParsingError) as single_call_exc:
                logger.warning(
                    "[MediaEnricher] Single-call batch failed (%s), falling back to standard batch",
                    single_call_exc,
                )

        model = GoogleBatchModel(api_key=api_key, model_name=model_name)
        try:
            return model.run_batch(requests)
        except (UsageLimitExceeded, ModelHTTPError, google_exceptions.GoogleAPICallError) as batch_exc:
            logger.warning(
                "Batch API failed (%s), falling back to individual calls for %d requests",
                batch_exc,
                len(requests),
            )
            return self._execute_individual(requests, task_map, model_name, api_key)

    def _execute_single_call(
        self,
        requests: list[dict[str, Any]],
        task_map: dict[str, dict[str, Any]],
        model_name: str,
        api_key: str,
    ) -> list[Any]:
        """Execute all media enrichments in a single API call."""
        client = genai.Client(api_key=api_key)

        if model_name.startswith("google-gla:"):
            model_name = model_name.removeprefix("google-gla:")

        parts: list[dict[str, Any]] = []
        filenames = []
        for req in requests:
            tag = req.get("tag")
            task = task_map.get(tag, {})
            payload = task.get("_parsed_payload", {})
            filename = payload.get("filename", tag)
            filenames.append(filename)

            contents = req.get("contents", [])
            for content in contents:
                for part in content.get("parts", []):
                    if "inlineData" in part:
                        parts.append({"inlineData": part["inlineData"]})
                    elif "fileData" in part:
                        parts.append({"fileData": part["fileData"]})

        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None
        combined_prompt = render_prompt(
            "enrichment.jinja",
            mode="media_batch",
            prompts_dir=prompts_dir,
            image_count=len(filenames),
            filenames_json=json.dumps(filenames),
            pii_prevention=getattr(self.ctx.config.privacy, "pii_prevention", None),
        ).strip()

        request_parts = [{"text": combined_prompt}, *parts]

        if self.worker.rotator:

            def call_with_model_and_key(model: str, api_key: str) -> str:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model,
                    contents=cast("Any", [{"parts": request_parts}]),
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                return response.text or ""

            response_text = self.worker.rotator.call_with_rotation(call_with_model_and_key)
        else:
            response = client.models.generate_content(
                model=model_name,
                contents=cast("Any", [{"parts": request_parts}]),
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            response_text = response.text if response.text else ""

        try:
            results_dict = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning("[MediaEnricher] Failed to parse JSON response: %s", e)
            msg = f"Failed to parse batch response: {e}"
            raise EnrichmentParsingError(msg) from e

        results = []
        for req in requests:
            tag = req.get("tag")
            task = task_map.get(tag, {})
            payload = task.get("_parsed_payload", {})
            filename = payload.get("filename", tag)

            enrichment = results_dict.get(filename, {})
            if enrichment:
                response_data = {
                    "text": json.dumps(
                        {
                            "slug": enrichment.get("slug", ""),
                            "description": enrichment.get("description", ""),
                            "alt_text": enrichment.get("alt_text", ""),
                            "filename": filename,
                        }
                    )
                }
                result = type(
                    "BatchResult",
                    (),
                    {"tag": tag, "response": response_data, "error": None},
                )()
            else:
                result = type(
                    "BatchResult",
                    (),
                    {"tag": tag, "response": None, "error": {"message": f"No result for {filename}"}},
                )()
            results.append(result)

        return results

    def _execute_individual(
        self,
        requests: list[dict[str, Any]],
        task_map: dict[str, dict[str, Any]],
        model_name: str,
        api_key: str,
    ) -> list[Any]:
        """Execute media enrichment requests individually."""
        client = genai.Client(api_key=api_key)

        if model_name.startswith("google-gla:"):
            model_name = model_name.removeprefix("google-gla:")

        results = []
        for req in requests:
            tag = req.get("tag")
            task = task_map.get(tag)
            if not task:
                continue

            try:
                contents = req.get("contents", [])
                config = req.get("config", {})
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(**config) if config else None,
                )
                result = type(
                    "BatchResult",
                    (),
                    {
                        "tag": tag,
                        "response": {"text": response.text} if response.text else None,
                        "error": None,
                    },
                )()
                results.append(result)
            except Exception as exc:
                logger.warning("[MediaEnricher] Individual call failed for %s: %s", tag, exc)
                result = type(
                    "BatchResult",
                    (),
                    {
                        "tag": tag,
                        "response": None,
                        "error": {"message": str(exc)},
                    },
                )()
                results.append(result)

        return results

    def _persist_results(self, results: list[Any], task_map: dict[str, dict[str, Any]]) -> int:
        new_rows = []
        replacements: list[tuple[str, str]] = []
        completed_task_ids: list[str] = []
        for res in results:
            task = task_map.get(res.tag)
            if not task:
                continue

            if res.error:
                self.task_store.mark_failed(task["task_id"], str(res.error))
                continue

            try:
                task_result = self._parse_result(res, task)
            except EnrichmentParsingError as exc:
                logger.warning("Enrichment parsing failed for task %s: %s", task.get("task_id"), exc)
                self.task_store.mark_failed(task["task_id"], str(exc))
                continue

            payload, output = task_result
            slug_value = output.slug
            markdown = output.markdown
            filename = payload["filename"]
            media_type = payload["media_type"]
            media_id = payload.get("media_id")

            staged_path = task.get("_staged_path")
            source_path = None
            if staged_path and Path(staged_path).exists():
                source_path = staged_path
            else:
                re_staged = self._stage_file(task, payload)
                if re_staged:
                    source_path = str(re_staged)
                else:
                    logger.warning("Could not stage media file for persistence: %s", filename)
                    self.task_store.mark_failed(task["task_id"], "Failed to stage media file")
                    continue

            from egregora.ops.media import get_media_subfolder

            extension = Path(filename).suffix
            media_subdir = get_media_subfolder(extension)
            final_filename = f"{slug_value}{extension}"
            suggested_path = f"media/{media_subdir}/{final_filename}"

            media_metadata = {
                "original_filename": payload.get("original_filename"),
                "filename": final_filename,
                "media_type": media_type,
                "slug": slug_value,
                "nav_exclude": True,
                "hide": ["navigation"],
                "source_path": source_path,
                "media_subdir": media_subdir,
            }

            media_doc = Document(
                content=b"",
                type=DocumentType.MEDIA,
                metadata=media_metadata,
                id=media_id if media_id else str(uuid.uuid4()),
                parent_id=None,
                suggested_path=suggested_path,
            )

            try:
                if self.ctx.library:
                    cast("Any", self.ctx.library).save(media_doc)
                elif self.ctx.output_sink:
                    self.ctx.output_sink.persist(media_doc)
                logger.info("Persisted enriched media: %s -> %s", filename, media_doc.metadata["filename"])
            except Exception as exc:
                logger.exception("Failed to persist media file %s", filename)
                self.task_store.mark_failed(task["task_id"], f"Persistence failed: {exc}")
                continue

            enrichment_metadata = {
                "filename": final_filename,
                "original_filename": payload.get("original_filename"),
                "media_type": media_type,
                "parent_path": suggested_path,
                "slug": slug_value,
                "title": output.title if output else slug_value.replace("-", " ").title(),
                "tags": output.tags if output else [],
                "date": datetime.now(UTC).isoformat(),
                "nav_exclude": True,
                "hide": ["navigation"],
            }

            doc_type = DocumentType.ENRICHMENT_MEDIA
            if media_type:
                if media_type.startswith("image"):
                    doc_type = DocumentType.ENRICHMENT_IMAGE
                elif media_type.startswith("video"):
                    doc_type = DocumentType.ENRICHMENT_VIDEO
                elif media_type.startswith("audio"):
                    doc_type = DocumentType.ENRICHMENT_AUDIO

            doc = Document(
                content=markdown,
                type=doc_type,
                metadata=enrichment_metadata,
                id=slug_value,
                parent_id=None,
            )

            if self.ctx.library:
                cast("Any", self.ctx.library).save(doc)
            elif self.ctx.output_sink:
                self.ctx.output_sink.persist(doc)

            metadata = payload["message_metadata"]
            row = create_enrichment_row(
                metadata, "Media", filename, doc.document_id, media_identifier=media_id
            )
            if row:
                new_rows.append(row)

            original_ref = payload.get("original_filename")
            if original_ref:
                media_subdir = "files"
                if media_type and media_type.startswith("image"):
                    media_subdir = "images"
                elif media_type and media_type.startswith("video"):
                    media_subdir = "videos"
                elif media_type and media_type.startswith("audio"):
                    media_subdir = "audio"

                new_path = f"media/{media_subdir}/{slug_value}{Path(filename).suffix}"
                replacements.append((original_ref, new_path))

            completed_task_ids.append(task["task_id"])

        if replacements:
            try:
                self._apply_batch_replacements(replacements)
            except Exception as exc:
                logger.error("Batch media update failed; aborting task completion: %s", exc)
                raise

        if completed_task_ids:
            if hasattr(self.task_store, "mark_completed_batch"):
                self.task_store.mark_completed_batch(completed_task_ids)
            else:
                for tid in completed_task_ids:
                    self.task_store.mark_completed(tid)

        if new_rows:
            try:
                t = ibis.memtable(new_rows)
                self.ctx.storage.write_table(t, "messages", mode="append")
                logger.info("Inserted %d media enrichment rows", len(new_rows))
            except (IbisError, duckdb.Error):
                logger.exception("Failed to insert media enrichment rows")

        return len(results)

    def _parse_result(self, res: Any, task: dict[str, Any]) -> tuple[dict[str, Any], EnrichmentOutput]:
        text = self._extract_text(res.response)
        try:
            clean_text = text.strip()
            clean_text = clean_text.removeprefix("```json")
            clean_text = clean_text.removeprefix("```")
            clean_text = clean_text.removesuffix("```")

            data = json.loads(clean_text.strip())
            slug = data.get("slug")
            markdown = data.get("markdown")
            title = data.get("title")
            tags = data.get("tags", [])

            payload = task["_parsed_payload"]
            filename = payload.get("filename", "")

            slug_value = normalize_slug(slug, payload["filename"]) if slug else None

            if not markdown and slug_value:
                description = data.get("description", "")
                alt_text = data.get("alt_text", "")
                ext = Path(filename).suffix
                final_filename = f"{slug_value}{ext}"
                if description or alt_text:
                    markdown = f"""# {slug_value}

![{alt_text}]({final_filename})

## Description
{description}

## Tags
"""

            if not slug_value or not markdown:
                msg = "Missing slug or markdown"
                raise EnrichmentParsingError(msg)

            output = EnrichmentOutput(slug=slug_value, markdown=markdown, title=title, tags=tags)
            return payload, output

        except (json.JSONDecodeError, EnrichmentSlugError) as exc:
            msg = f"Failed to parse media result for task {task.get('task_id')}: {exc}"
            raise EnrichmentParsingError(msg) from exc

    def _extract_text(self, response: dict[str, Any] | None) -> str:
        if not response:
            return ""
        if "text" in response:
            return response["text"]
        texts: list[str] = []
        for cand in response.get("candidates") or []:
            content = cand.get("content") or {}
            texts.extend(part["text"] for part in content.get("parts") or [] if "text" in part)
        return "\n".join(texts)

    def _apply_batch_replacements(self, replacements: list[tuple[str, str]]) -> None:
        """Apply a batch of media reference replacements."""
        if not replacements:
            return

        try:
            expr = "text"
            params = []
            for old_ref, new_ref in replacements:
                expr = f"replace({expr}, ?, ?)"
                params.extend([old_ref, new_ref])

            pattern = "|".join([re.escape(old) for old, _ in replacements])
            params.append(pattern)
            query = f"UPDATE messages SET text = {expr} WHERE regexp_matches(text, ?)"

            self.ctx.storage.execute_sql(query, params)
            logger.info("Applied batch update for %d media references", len(replacements))

        except (duckdb.Error, Exception) as exc:
            logger.warning("Failed to apply batch media replacements: %s", exc)
            raise

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
