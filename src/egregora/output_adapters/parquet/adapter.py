import builtins
import json
import logging
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import ibis

from egregora.data_primitives import Document, DocumentMetadata, DocumentType
from egregora.data_primitives.protocols import UrlConvention
from egregora.output_adapters.base import OutputAdapter
from egregora.output_adapters.conventions import StandardUrlConvention
from egregora.output_adapters.parquet.schema import DOCUMENT_PARQUET_SCHEMA

logger = logging.getLogger(__name__)


class ParquetAdapter(OutputAdapter):
    """Data Lake adapter: writes content as structured Parquet files."""

    def __init__(self) -> None:
        self.data_dir: Path | None = None
        self._url_convention = StandardUrlConvention()
        self.site_root: Path | None = None

    @property
    def format_type(self) -> str:
        return "parquet"

    @property
    def url_convention(self) -> UrlConvention:
        return self._url_convention

    def initialize(self, site_root: Path) -> None:
        """Initialize the data directory structure."""
        self.site_root = site_root
        self.data_dir = self.site_root / "data"

        # Create partition directories
        for doc_type in [t.value for t in DocumentType]:
            (self.data_dir / f"type={doc_type}").mkdir(parents=True, exist_ok=True)

    def supports_site(self, site_root: Path) -> bool:
        """Check if this looks like a Parquet dataset."""
        return (site_root / "data").exists()

    def persist(self, document: Document) -> None:
        """Write the document as an atomic Parquet file."""
        if not self.data_dir:
            msg = "Adapter not initialized"
            raise RuntimeError(msg)

        meta = document.metadata
        doc_type = document.type.value

        # 1. Prepare Data Row
        # We map the Document object to the strict Schema defined above
        row = {
            "id": document.document_id,
            "slug": meta.get("slug", document.document_id[:8]),
            "type": doc_type,
            "title": meta.get("title", "Untitled"),
            "content": self._decode_content(document.content),
            "summary": meta.get("summary", ""),
            "published_date": meta.get("date"),
            "authors": meta.get("authors", []),
            "tags": meta.get("tags", []),
            "metadata_json": json.dumps(self._sanitize_json(meta)),
            "created_at": document.created_at,
            "updated_at": datetime.now(),
        }

        # 2. Create Ibis Table (Validation)
        # ibis.memtable handles type conversion automatically based on schema
        table = ibis.memtable([row], schema=DOCUMENT_PARQUET_SCHEMA)

        # 3. Determine Output Path (Hive Partitioning Style)
        # data/type=post/id=<uuid>.parquet
        filename = f"id={document.document_id}.parquet"
        output_path = self.data_dir / f"type={doc_type}" / filename

        # 4. Write using PyArrow engine (via Ibis)
        # We use to_parquet directly on the executed frame for granular control
        # or let Ibis handle it. Here we use Ibis -> PyArrow for safety.
        table.to_parquet(output_path)

        logger.debug(f"Persisted parquet: {output_path}")

    def get(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Read a single Parquet file back into a Document."""
        if not self.data_dir:
            return None

        # Try finding by ID first (fastest)
        target_file = self.data_dir / f"type={doc_type.value}" / f"id={identifier}.parquet"

        if not target_file.exists():
            # Fallback: Scan for slug (slower, requires DuckDB scan)
            # In a real data lake, you'd use an Iceberg/Delta catalog for this.
            # For local files, we skip implementing full scan for brevity unless needed.
            return None

        # Read back
        t = ibis.read_parquet(target_file)
        data = t.execute().to_dict(orient="records")[0]

        return Document(
            content=data["content"],
            type=doc_type,
            metadata={**json.loads(data["metadata_json"]), "title": data["title"], "slug": data["slug"]},
        )

    def list(self, doc_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        """Yield metadata by scanning the parquet directory structure."""
        if not self.data_dir:
            return

        # Define types to scan
        types_to_scan = [doc_type] if doc_type else DocumentType

        for dtype in types_to_scan:
            type_str = dtype.value if isinstance(dtype, DocumentType) else str(dtype)
            path = self.data_dir / f"type={type_str}"

            if not path.exists():
                continue

            for p_file in path.glob("*.parquet"):
                # Optimization: Read ONLY metadata columns, not content
                # DuckDB is incredibly fast at this
                try:
                    t = ibis.read_parquet(p_file)
                    meta = t.select("id", "type", "metadata_json").execute().iloc[0]

                    yield DocumentMetadata(
                        identifier=meta["id"],
                        doc_type=DocumentType(meta["type"]),
                        metadata=json.loads(meta["metadata_json"]),
                    )
                except Exception as e:
                    logger.warning(f"Failed to read parquet {p_file}: {e}")

    def documents(self) -> Iterator[Document]:
        for meta in self.list():
            doc = self.get(meta.doc_type, meta.identifier)
            if doc:
                yield doc

    def _decode_content(self, content: str | bytes) -> str:
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="ignore")
        return content

    def _sanitize_json(self, data: dict) -> dict:
        """Ensure metadata is JSON serializable."""
        clean = {}
        for k, v in data.items():
            if isinstance(v, (datetime, date)):
                clean[k] = v.isoformat()
            else:
                clean[k] = v
        return clean

    # Protocol Requirements
    def get_markdown_extensions(self) -> builtins.list[str]:
        return []

    def get_format_instructions(self) -> str:
        return "Focus on rich metadata."

    def scaffold_site(self, site_root: Path, site_name: str, **kwargs) -> tuple[Path, bool]:
        self.initialize(site_root)
        if self.data_dir is None:
            msg = "Adapter not initialized properly, data_dir is None."
            raise RuntimeError(msg)
        return self.data_dir, True

    def resolve_paths(self, site_root: Path) -> Any:
        return {"site_root": site_root}
