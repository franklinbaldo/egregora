"""Eleventy output adapter using Arrow/Parquet for data storage.

Writes per-window Parquet files to filesystem. Eleventy reads these at build time
to generate static pages without intermediate markdown files.

Architecture:
    output/
      data/
        window_0.parquet
        window_1.parquet
        window_2.parquet
      eleventy/
        src/_data/documents.js  # Loads all window_*.parquet
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.base import OutputAdapter, SiteConfiguration

logger = logging.getLogger(__name__)


def _ensure_cache_dir(path: Path) -> Path:
    """Ensure the cache directory exists and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _default_documents_table() -> ibis.expr.types.Table:
    """Return an empty documents table with correct schema."""
    schema = ibis.schema({"storage_identifier": "string", "mtime_ns": "int64"})
    return ibis.memtable([], schema=schema)


class EleventyArrowAdapter:
    """Output adapter that writes per-window Parquet files for Eleventy.

    Each window produces a separate Parquet file with all documents created
    during that window. Eleventy's data loader reads all files at build time.

    Benefits:
    - No intermediate markdown files
    - Memory efficient (per-window buffering)
    - Incremental publishing (add new windows without rewriting)
    - Column-oriented storage (efficient filtering/sorting)

    Examples:
        >>> from pathlib import Path
        >>> adapter = EleventyArrowAdapter(site_root=Path("output"), url_context=None)
        >>>
        >>> # Pipeline calls serve for each document (must have source_window set)
        >>> doc1.source_window = "2025-01-11 10:00 to 12:00"
        >>> doc2.source_window = "2025-01-11 10:00 to 12:00"
        >>> adapter.serve(doc1)
        >>> adapter.serve(doc2)
        >>>
        >>> # Pipeline calls finalize_window after processing
        >>> adapter.finalize_window("2025-01-11 10:00 to 12:00", [], [], {"window_index": 0})
        >>> # Creates output/data/window_0.parquet

    """

    def __init__(self, site_root: Path, url_context: Any) -> None:
        """Initialize Eleventy Arrow adapter.

        Args:
            site_root: Root directory for output
            url_context: Context for URL generation (not used, for interface compatibility)

        Side Effects:
            Creates data directory: {site_root}/data/

        """
        self.site_root = site_root
        self._url_context = url_context

        # Data directory for Parquet files
        self.data_dir = site_root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Per-window buffers: window_label -> list of documents
        self._buffers: dict[str, list[Document]] = {}

        # Window counter for sequential naming
        self._window_counter = 0

        logger.info("Initialized EleventyArrowAdapter at %s", site_root)

    def serve(self, document: Document) -> None:
        """Buffer document for later batch write.

        Documents are grouped by source_window and accumulated in memory
        until finalize_window() writes them to Parquet.

        Args:
            document: Document to buffer (must have source_window set)

        Raises:
            RuntimeError: If document.source_window is not set

        """
        window_label = document.source_window
        if window_label is None:
            msg = "Document must have source_window set for EleventyArrowAdapter"
            raise RuntimeError(msg)

        # Create buffer for this window if needed
        if window_label not in self._buffers:
            self._buffers[window_label] = []

        self._buffers[window_label].append(document)
        logger.debug(
            "Buffered %s document (id=%s) for window %s",
            document.type.value,
            document.document_id[:8],
            window_label,
        )

    def prepare_window(self, window_label: str, _window_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Optional hook called before window processing.

        Not required - EleventyArrowAdapter auto-creates buffers on serve().
        Included for interface compatibility with OutputAdapter protocol.

        Args:
            window_label: Window identifier (e.g., "2025-01-11 10:00 to 12:00")
            _window_data: Optional metadata (unused)

        Returns:
            Context dict with window_index for finalize_window()

        """
        window_index = self._window_counter
        self._window_counter += 1

        logger.info("Prepared window %s (index=%d)", window_label, window_index)
        return {"window_index": window_index}

    def finalize_window(
        self,
        window_label: str,
        _posts_created: list[str],
        _profiles_updated: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write buffered documents to Parquet file.

        Creates {data_dir}/window_{index}.parquet with all documents
        from this window.

        Args:
            window_label: Window identifier
            _posts_created: Unused (for interface compatibility)
            _profiles_updated: Unused (for interface compatibility)
            metadata: Context from prepare_window (contains window_index)

        Side Effects:
            Writes Parquet file to filesystem
            Clears buffer for this window

        """
        # Check if we have documents for this window
        if window_label not in self._buffers or not self._buffers[window_label]:
            logger.info("Window %s: no documents to write", window_label)
            return

        buffer = self._buffers[window_label]

        # Get window index from prepare_window context (or auto-assign)
        window_index = metadata.get("window_index") if metadata else None
        if window_index is None:
            window_index = self._window_counter
            self._window_counter += 1

        # Convert buffer to Arrow table
        table = self._documents_to_arrow(buffer)

        # Write to Parquet
        parquet_path = self.data_dir / f"window_{window_index}.parquet"
        pq.write_table(table, parquet_path, compression="snappy")

        logger.info(
            "Window %s: wrote %d documents to %s (%.2f KB)",
            window_label,
            len(buffer),
            parquet_path.name,
            parquet_path.stat().st_size / 1024,
        )

        # Clear buffer for this window
        del self._buffers[window_label]

    def _documents_to_arrow(self, documents: list[Document]) -> pa.Table:
        """Convert Documents to Arrow table with columnar schema.

        Schema:
            id: string (UUID)
            slug: string (URL slug)
            kind: string (post, profile, journal, enrichment_url, enrichment_media, media)
            title: string (document title)
            body_md: string (markdown content)
            created_at: string (ISO 8601 timestamp)
            metadata: string (JSON-encoded metadata dict)
            parent_id: string (parent document ID, nullable)

        Args:
            documents: List of documents to convert

        Returns:
            Arrow table with schema above

        """
        data = {
            "id": [d.document_id for d in documents],
            "slug": [d.metadata.get("slug", "") for d in documents],
            "kind": [d.type.value for d in documents],
            "title": [d.metadata.get("title", "") for d in documents],
            "body_md": [d.content for d in documents],
            "created_at": [d.created_at.isoformat() for d in documents],
            "metadata": [json.dumps(d.metadata) for d in documents],
            "parent_id": [d.parent_id or "" for d in documents],
        }

        return pa.Table.from_pydict(data)

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Read document by type and identifier.

        Scans all Parquet files to find matching document. This is a full scan,
        so use sparingly. Eleventy reads Parquet at build time, not runtime.

        Args:
            doc_type: Type of document to find
            identifier: Document ID or slug

        Returns:
            Document if found, None otherwise

        """
        # Scan all window Parquet files
        for parquet_file in sorted(self.data_dir.glob("window_*.parquet")):
            table = pq.read_table(parquet_file)

            # Filter by type
            df = table.to_pandas()
            matches = df[df["kind"] == doc_type.value]

            # Filter by identifier (include document-type metadata identifiers)
            for _, row in matches.iterrows():
                metadata = self._deserialize_metadata(row.get("metadata"))
                if identifier in self._identifier_candidates(doc_type, row, metadata):
                    # Reconstruct Document
                    from egregora.data_primitives.document import Document

                    created_at = row.get("created_at")
                    parsed_created_at = (
                        datetime.fromisoformat(created_at)
                        if isinstance(created_at, str)
                        else datetime.now(tz=UTC)
                    )

                    return Document(
                        content=row["body_md"],
                        type=DocumentType(row["kind"]),
                        metadata=metadata,
                        parent_id=row["parent_id"] if row["parent_id"] else None,
                        created_at=parsed_created_at,
                    )

        return None

    @staticmethod
    def _deserialize_metadata(raw: Any) -> dict[str, Any]:
        """Best-effort JSON decode for stored metadata."""
        if isinstance(raw, str) and raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Failed to decode document metadata; returning empty dict")
        return {}

    @staticmethod
    def _identifier_candidates(doc_type: DocumentType, row: Any, metadata: dict[str, Any]) -> set[str]:
        """Return all identifiers that should match the given document."""
        candidates: set[str] = set()

        # Basic identifiers common across document types
        for key in ("id", "slug"):
            value = row.get(key)
            if isinstance(value, str) and value:
                candidates.add(value)

        # Document-type specific identifiers
        if doc_type == DocumentType.PROFILE:
            for key in ("uuid", "author_uuid"):
                value = metadata.get(key)
                if isinstance(value, str) and value:
                    candidates.add(value)
        elif doc_type == DocumentType.JOURNAL:
            value = metadata.get("window_label")
            if isinstance(value, str) and value:
                candidates.add(value)
        elif doc_type == DocumentType.POST:
            value = metadata.get("slug")
            if isinstance(value, str) and value:
                candidates.add(value)

        return candidates

    def list_documents(self, doc_type: DocumentType | None = None) -> list[Document]:
        """List all documents, optionally filtered by type.

        Scans all Parquet files and returns matching documents.

        Args:
            doc_type: Optional document type filter

        Returns:
            List of documents

        """
        from egregora.data_primitives.document import Document

        documents: list[Document] = []

        # Scan all window Parquet files
        for parquet_file in sorted(self.data_dir.glob("window_*.parquet")):
            table = pq.read_table(parquet_file)
            df = table.to_pandas()

            # Filter by type if specified
            if doc_type is not None:
                df = df[df["kind"] == doc_type.value]

            # Convert to Documents
            for _, row in df.iterrows():
                metadata = self._deserialize_metadata(row.get("metadata"))
                created_at = row.get("created_at")
                parsed_created_at = (
                    datetime.fromisoformat(created_at)
                    if isinstance(created_at, str)
                    else datetime.now(tz=UTC)
                )

                documents.append(
                    Document(
                        content=row["body_md"],
                        type=DocumentType(row["kind"]),
                        metadata=metadata,
                        parent_id=row["parent_id"] if row["parent_id"] else None,
                        created_at=parsed_created_at,
                    )
                )

        return documents


class EleventyArrowOutputAdapter(OutputAdapter):
    """Registry-compatible adapter that bridges legacy and document interfaces."""

    def __init__(self) -> None:
        self._site_root: Path | None = None
        self._eleventy: EleventyArrowAdapter | None = None
        self._document_cache: dict[str, Document] = {}
        self._cache_dir: Path | None = None

    # ===== OutputAdapter abstract methods =====

    @property
    def format_type(self) -> str:
        return "eleventy-arrow"

    def initialize(self, site_root: Path) -> None:
        self._site_root = site_root
        self._cache_dir = _ensure_cache_dir(site_root / ".egregora" / "cache" / "eleventy-arrow")
        self._eleventy = EleventyArrowAdapter(site_root=site_root, url_context=None)
        self._refresh_document_cache()

    def scaffold_site(self, site_root: Path, site_name: str, **kwargs: object) -> tuple[Path, bool]:
        template_dir = Path(__file__).with_name("eleventy_template")
        eleventy_root = site_root / "eleventy"
        was_created = not eleventy_root.exists()
        eleventy_root.mkdir(parents=True, exist_ok=True)

        # Copy template files without clobbering user customizations
        for item in template_dir.iterdir():
            target = eleventy_root / item.name
            _copytree(item, target)

        # Ensure data directory exists for Parquet output
        (site_root / "data").mkdir(parents=True, exist_ok=True)

        config_file = eleventy_root / ".eleventy.js"
        return config_file, was_created

    def resolve_paths(self, site_root: Path) -> SiteConfiguration:
        eleventy_root = site_root / "eleventy"
        docs_dir = eleventy_root / "src"
        posts_dir = docs_dir / "posts"
        profiles_dir = docs_dir / "profiles"
        media_dir = site_root / "data"
        additional_paths = {
            "eleventy_root": eleventy_root,
            "data_dir": site_root / "data",
        }

        return SiteConfiguration(
            site_root=site_root,
            site_name=site_root.name,
            docs_dir=docs_dir,
            posts_dir=posts_dir,
            profiles_dir=profiles_dir,
            media_dir=media_dir,
            config_file=eleventy_root / ".eleventy.js",
            additional_paths=additional_paths,
        )

    def write_post(self, content: str, metadata: dict[str, Any], output_dir: Path, **kwargs: object) -> str:
        msg = "EleventyArrowOutputAdapter does not support legacy write_post(); use serve() with Document."
        raise NotImplementedError(msg)

    def write_profile(
        self, author_id: str, profile_data: dict[str, Any], profiles_dir: Path, **kwargs: object
    ) -> str:
        msg = "EleventyArrowOutputAdapter does not support legacy write_profile(); use serve() with Document."
        raise NotImplementedError(msg)

    def load_config(self, site_root: Path) -> dict[str, Any]:
        eleventy_root = site_root / "eleventy"
        package_json = eleventy_root / "package.json"
        if package_json.exists():
            return json.loads(package_json.read_text(encoding="utf-8"))
        return {}

    def supports_site(self, site_root: Path) -> bool:
        return (site_root / "eleventy" / ".eleventy.js").exists() and (site_root / "data").exists()

    def get_markdown_extensions(self) -> list[str]:
        return ["gfm", "tables", "fenced_code"]

    def get_format_instructions(self) -> str:
        return (
            "## Output Format: Eleventy + Arrow\n\n"
            "This site stores documents in Parquet files under `data/window_*.parquet`. "
            "Eleventy loads all documents at build time and renders templates from the bundled "
            "`eleventy` directory. Write Markdown content (no YAML frontmatter required); metadata "
            "is stored separately in Arrow columns."
        )

    def list_documents(self) -> ibis.expr.types.Table:
        self._ensure_initialized()
        self._refresh_document_cache()

        if not self._document_cache:
            return _default_documents_table()

        rows = []
        for document in self._document_cache.values():
            mtime_ns = int(document.created_at.timestamp() * 1_000_000_000)
            rows.append(
                {
                    "storage_identifier": document.document_id,
                    "mtime_ns": mtime_ns,
                }
            )

        return ibis.memtable(rows)

    def resolve_document_path(self, identifier: str) -> Path:
        self._ensure_initialized()
        if self._cache_dir is None:
            msg = "EleventyArrowOutputAdapter not initialized"
            raise RuntimeError(msg)

        document = self._document_cache.get(identifier)
        if document is None:
            self._refresh_document_cache()
            document = self._document_cache.get(identifier)

        if document is None:
            msg = f"Document with identifier {identifier} not found"
            raise ValueError(msg)

        cache_file = self._cache_dir / f"{identifier}.md"
        frontmatter = {
            "id": document.document_id,
            "type": document.type.value,
            "created_at": document.created_at.isoformat(),
            "metadata": document.metadata,
        }

        with cache_file.open("w", encoding="utf-8") as fh:
            fh.write("---\n")
            yaml.safe_dump(frontmatter, fh, sort_keys=False)
            fh.write("---\n\n")
            fh.write(document.content)
            fh.write("\n")

        return cache_file

    @property
    def posts(self) -> Any:  # type: ignore[override]
        msg = "EleventyArrowOutputAdapter does not expose legacy PostStorage; use serve() with Document."
        raise RuntimeError(msg)

    @property
    def profiles(self) -> Any:  # type: ignore[override]
        msg = "EleventyArrowOutputAdapter does not expose legacy ProfileStorage; use serve() with Document."
        raise RuntimeError(msg)

    @property
    def journals(self) -> Any:  # type: ignore[override]
        msg = "EleventyArrowOutputAdapter does not expose legacy JournalStorage; use serve() with Document."
        raise RuntimeError(msg)

    @property
    def enrichments(self) -> Any:  # type: ignore[override]
        msg = (
            "EleventyArrowOutputAdapter does not expose legacy EnrichmentStorage; use serve() with Document."
        )
        raise RuntimeError(msg)

    # ===== Modern document-based helpers =====

    def serve(self, document: Document) -> None:
        self._ensure_initialized()
        assert self._eleventy is not None  # For type checkers
        self._eleventy.serve(document)

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
        self._ensure_initialized()
        assert self._eleventy is not None
        return self._eleventy.read_document(doc_type, identifier)

    def prepare_window(
        self, window_label: str, _window_data: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        self._ensure_initialized()
        assert self._eleventy is not None
        return self._eleventy.prepare_window(window_label, _window_data)

    def finalize_window(
        self,
        window_label: str,
        posts_created: list[str],
        profiles_updated: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._ensure_initialized()
        assert self._eleventy is not None
        self._eleventy.finalize_window(window_label, posts_created, profiles_updated, metadata)
        self._refresh_document_cache()

    # ===== Internal helpers =====

    def _ensure_initialized(self) -> None:
        if self._eleventy is None or self._site_root is None:
            msg = "EleventyArrowOutputAdapter.initialize() must be called before use"
            raise RuntimeError(msg)

    def _refresh_document_cache(self) -> None:
        if self._eleventy is None:
            return
        documents = self._eleventy.list_documents()
        self._document_cache = {doc.document_id: doc for doc in documents}


def _copytree(src: Path, dst: Path) -> None:
    """Copy directory tree while preserving existing files."""
    if src.is_file():
        if dst.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        return

    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        _copytree(child, target)
