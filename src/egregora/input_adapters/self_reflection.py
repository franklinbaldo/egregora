"""Adapter that reprocesses an existing Egregora site as input."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import ibis
import yaml

from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.input_adapters.base import AdapterMeta, InputAdapter
from egregora.output_adapters.base import OutputAdapter
from egregora.utils.frontmatter_utils import parse_frontmatter_file
from egregora.utils.paths import slugify

logger = logging.getLogger(__name__)

AUTHOR_NAMESPACE = UUID("52ef49ac-b9f7-48b9-8f37-8db2ca4c7f4f")
EVENT_NAMESPACE = UUID("3d99325f-85e5-4c4b-9a85-4e80bc9a6d33")


class SelfInputAdapter(InputAdapter):
    """Treat the current blog output as the source for another run."""

    source_slug = "self"

    @property
    def source_name(self) -> str:
        return "Egregora Self-Reflection"

    @property
    def source_identifier(self) -> str:
        return self.source_slug

    @property
    def content_summary(self) -> str:
        return (
            "Previously published posts from your Egregora site. The adapter feeds the rendered "
            "Markdown back into the pipeline so the writer can reason about its own past outputs."
        )

    @property
    def generation_instructions(self) -> str:
        today = date.today().isoformat()
        return (
            "You are reviewing posts that you already wrote. Only create a new post when you can "
            "draw genuinely novel inferences or deliver a fresh synthesis that was not already captured. "
            f"If you do publish something new, tag it with today's date ({today}) in the metadata instead of "
            "reusing the historical window date."
        )

    def get_adapter_metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name=self.source_name,
            version="0.1.0",
            source=self.source_identifier,
            doc_url="https://github.com/franklinbaldo/egregora",
            ir_version="v1",
        )

    def parse(
        self,
        input_path: Path,
        *,
        output_adapter: OutputAdapter | None = None,
        timezone: str | None = None,
        **_: Any,
    ) -> ibis.Table:
        docs_dir, site_root = self._resolve_docs_dir(input_path)
        markdown_paths = self._gather_markdown_paths(
            docs_dir, output_adapter=output_adapter
        )
        if not markdown_paths:
            msg = f"No markdown posts found under {docs_dir}"
            raise RuntimeError(msg)

        site_name = self._load_site_name(site_root)
        records: list[dict[str, Any]] = []
        for markdown_path in markdown_paths:
            try:
                metadata, body = parse_frontmatter_file(markdown_path)
            except (OSError, ValueError, yaml.YAMLError) as exc:
                logger.debug("Skipping %s due to parsing error: %s", markdown_path, exc)
                continue
            slug = self._resolve_slug(metadata, markdown_path)
            timestamp = self._resolve_timestamp(metadata.get("date"), markdown_path, timezone)
            authors = metadata.get("authors") or []
            if isinstance(authors, str):
                author_label = authors
            elif isinstance(authors, list) and authors:
                author_label = str(authors[0])
            else:
                author_label = site_name
            author_uuid = str(uuid5(AUTHOR_NAMESPACE, author_label.lower()))
            attrs = self._sanitize_metadata(metadata, markdown_path)
            attrs_json = json.dumps(attrs)
            text = body.strip() or attrs.get("summary") or f"Existing post: {metadata.get('title', slug)}"
            try:
                relative_path = str(markdown_path.relative_to(docs_dir))
            except ValueError:
                relative_path = str(markdown_path.name)
            event_id = str(uuid5(EVENT_NAMESPACE, relative_path))

            records.append(
                {
                    "event_id": event_id,
                    "tenant_id": site_name,
                    "source": self.source_identifier,
                    "thread_id": slug,
                    "msg_id": f"self-{slug}",
                    "ts": timestamp,
                    "author_raw": author_label,
                    "author_uuid": author_uuid,
                    "text": text,
                    "media_url": None,
                    "media_type": None,
                    "attrs": attrs_json,
                    "pii_flags": None,
                    "created_at": timestamp,
                    "created_by_run": "adapter:self-reflection",
                }
            )

        return ibis.memtable(records, schema=IR_MESSAGE_SCHEMA)

    def _gather_markdown_paths(
        self,
        docs_dir: Path,
        *,
        output_adapter: OutputAdapter | None = None,
    ) -> list[Path]:
        """Return candidate markdown files for self-reflection ingestion."""
        if output_adapter:
            candidate_paths = self._collect_from_output_adapter(output_adapter)
            if candidate_paths:
                return candidate_paths

        posts_dir = docs_dir / "posts"
        if not posts_dir.is_dir():
            raise FileNotFoundError(f"Docs directory {docs_dir} does not contain a posts/ directory")

        return [
            path
            for path in posts_dir.rglob("*.md")
            if path.name not in {"index.md", "tags.md"}
        ]

    def _collect_from_output_adapter(self, output_adapter: OutputAdapter) -> list[Path]:
        """Collect markdown paths via the output adapter rather than crawling directories."""
        table = output_adapter.list_documents()
        try:
            records = table.execute().to_dict("records")
        except Exception:
            return []

        seen: set[Path] = set()
        markdown_paths: list[Path] = []
        for record in records:
            identifier = record.get("storage_identifier")
            if not identifier:
                continue
            try:
                resolved = output_adapter.resolve_document_path(identifier)
            except Exception:
                continue
            path = Path(resolved)
            if path.suffix.lower() != ".md":
                continue
            if path.name in {"index.md", "tags.md"}:
                continue
            if path in seen:
                continue
            seen.add(path)
            markdown_paths.append(path)
        return markdown_paths

    def get_metadata(self, input_path: Path, **_: Any) -> dict[str, Any]:
        _, site_root = self._resolve_docs_dir(input_path)
        return {"group_name": self._load_site_name(site_root)}

    def _resolve_docs_dir(self, input_path: Path) -> tuple[Path, Path]:
        resolved = input_path.expanduser().resolve()
        docs_dir = resolved / "docs"
        if resolved.is_dir() and docs_dir.is_dir():
            return docs_dir, resolved
        if resolved.is_dir() and resolved.name == "docs":
            return resolved, resolved.parent
        if resolved.is_dir() and (resolved / ".egregora").is_dir():
            return resolved, resolved
        msg = f"Input path {input_path} must be a site root or docs directory"
        raise FileNotFoundError(msg)

    def _load_site_name(self, site_root: Path) -> str:
        mkdocs_candidates = [site_root / "mkdocs.yml", site_root / ".egregora" / "mkdocs.yml"]
        for candidate in mkdocs_candidates:
            if not candidate.exists():
                continue
            try:
                data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:  # pragma: no cover - defensive
                logger.debug("Failed to parse %s: %s", candidate, exc)
                continue
            name = data.get("site_name") if isinstance(data, dict) else None
            if name:
                return str(name)
        return site_root.name

    def _resolve_slug(self, metadata: dict[str, Any], path: Path) -> str:
        slug_value = metadata.get("slug")
        if isinstance(slug_value, str) and slug_value.strip():
            return slugify(slug_value)
        return slugify(path.stem)

    def _resolve_timestamp(self, value: Any, path: Path, timezone: str | None) -> datetime:
        if isinstance(value, datetime):
            ts = value
        elif isinstance(value, date):
            ts = datetime.combine(value, datetime.min.time())
        elif isinstance(value, str) and value.strip():
            try:
                ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.strptime(value, "%Y-%m-%d")
        else:
            ts = datetime.fromtimestamp(path.stat().st_mtime)

        if ts.tzinfo is None:
            if timezone:
                try:
                    from zoneinfo import ZoneInfo

                    ts = ts.replace(tzinfo=ZoneInfo(timezone))
                except Exception:  # pragma: no cover - defensive
                    ts = ts.replace(tzinfo=UTC)
            else:
                ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)

    def _sanitize_metadata(self, metadata: dict[str, Any], markdown_path: Path) -> dict[str, Any]:
        sanitized: dict[str, Any] = {key: self._serialize_value(value) for key, value in metadata.items()}
        sanitized.setdefault("source_path", str(markdown_path))
        return sanitized

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize_value(val) for key, val in value.items()}
        return value
