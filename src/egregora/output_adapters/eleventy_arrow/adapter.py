from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import ibis
import pandas as pd

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.base import OutputAdapter, SiteConfiguration

logger = logging.getLogger(__name__)


class EleventyArrowOutputAdapter(OutputAdapter):
    """Write windowed documents into Parquet files consumable by Eleventy."""

    def __init__(self, site_root: Path | None = None, url_context: Any = None) -> None:
        self.site_root = site_root
        self.url_context = url_context
        self._buffers: dict[str, list[Document]] = {}

    # ------------------------------------------------------------------
    # OutputAdapter abstract API
    # ------------------------------------------------------------------
    def scaffold_site(self, site_root: Path, site_name: str, **kwargs: object) -> tuple[Path, bool]:
        data_dir = site_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir, True

    def resolve_paths(self, site_root: Path) -> SiteConfiguration:
        docs_dir = site_root
        return SiteConfiguration(
            site_root=site_root,
            site_name=site_root.name,
            docs_dir=docs_dir,
            posts_dir=docs_dir / "posts",
            profiles_dir=docs_dir / "profiles",
            media_dir=docs_dir / "media",
            config_file=None,
            additional_paths={"data": docs_dir / "data"},
        )

    def write_post(self, content: str, metadata: dict[str, Any], output_dir: Path, **kwargs: object) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{metadata.get('slug', 'post')}.md"
        target.write_text(content, encoding="utf-8")
        return str(target)

    def write_profile(
        self, author_id: str, profile_data: dict[str, Any], profiles_dir: Path, **kwargs: object
    ) -> str:
        profiles_dir.mkdir(parents=True, exist_ok=True)
        target = profiles_dir / f"{author_id}.md"
        target.write_text(json.dumps(profile_data, indent=2), encoding="utf-8")
        return str(target)

    def load_config(self, site_root: Path) -> dict[str, Any]:
        config_path = site_root / "eleventy.config.json"
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
        return {}

    def supports_site(self, site_root: Path) -> bool:
        return (site_root / "data").exists()

    @property
    def format_type(self) -> str:
        return "eleventy-arrow"

    def get_markdown_extensions(self) -> list[str]:
        return []

    def get_format_instructions(self) -> str:
        return "Use Eleventy-style slugs and lightweight markdown."

    def list_documents(self) -> "ibis.Table":  # type: ignore[override]
        empty = pd.DataFrame(columns=["storage_identifier", "mtime_ns"])
        return ibis.memtable(empty)

    def resolve_document_path(self, identifier: str) -> Path:
        if not self.site_root:
            msg = "Adapter not initialized"
            raise ValueError(msg)
        return (self.site_root / identifier).resolve()

    def initialize(self, site_root: Path) -> None:
        self.site_root = site_root
        (site_root / "data").mkdir(parents=True, exist_ok=True)

    def serve(self, document: Document) -> None:
        window = document.source_window or "default"
        self._buffers.setdefault(window, []).append(document)

    def prepare_window(self, window_label: str) -> dict[str, Any]:
        return {"window": window_label, "count": len(self._buffers.get(window_label, []))}

    def _documents_to_frame(self, window_label: str) -> pd.DataFrame:
        documents = self._buffers.get(window_label, [])
        rows = []
        for doc in documents:
            slug = doc.metadata.get("slug") or doc.metadata.get("uuid") or doc.metadata.get("id")
            rows.append(
                {
                    "id": doc.document_id,
                    "slug": slug,
                    "kind": doc.type.value,
                    "body_md": doc.content,
                    "metadata": doc.metadata,
                    "source_window": doc.source_window,
                    "created_at": doc.created_at,
                }
            )
        return pd.DataFrame(rows)

    def finalize_window(
        self,
        window_label: str,
        posts: list[Document],
        profiles: list[Document],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.site_root:
            msg = "Adapter not initialized"
            raise ValueError(msg)

        if posts:
            for doc in posts:
                self.serve(doc)
        if profiles:
            for doc in profiles:
                self.serve(doc)

        df = self._documents_to_frame(window_label)
        data_dir = self.site_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_path = data_dir / f"{window_label}.parquet"
        df.to_parquet(output_path, index=False)

    def read_document(self, document_type: DocumentType, identifier: str) -> Document | None:
        if not self.site_root:
            msg = "Adapter not initialized"
            raise ValueError(msg)

        data_dir = self.site_root / "data"
        frames = []
        for parquet_file in sorted(data_dir.glob("*.parquet")):
            frames.append(pd.read_parquet(parquet_file))
        if not frames:
            return None

        combined = pd.concat(frames, ignore_index=True)
        subset = combined[
            (combined["kind"] == document_type.value) & (combined["slug"].astype(str) == identifier)
        ]
        if subset.empty:
            return None

        row = subset.iloc[0]
        return Document(
            content=row["body_md"],
            type=document_type,
            metadata=row["metadata"] if isinstance(row["metadata"], dict) else {},
            created_at=row.get("created_at"),
            source_window=row.get("source_window"),
        )


class EleventyArrowAdapter(EleventyArrowOutputAdapter):
    """Alias kept for backwards compatibility with existing imports."""

    pass
