import builtins
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from egregora_v3.core.types import Document, DocumentType, Entry, Feed, Link


@runtime_checkable
class InputAdapter(Protocol):
    """Parses a source input into a stream of Entries."""

    def parse(self, source: Path) -> Iterator[Entry]: ...


@runtime_checkable
class DocumentRepository(Protocol):
    """Persists and retrieves Document and Entry primitives."""

    # Documents
    def save(self, doc: Document) -> Document: ...
    def get(self, doc_id: str) -> Document | None: ...
    def list(self, *, doc_type: DocumentType | None = None) -> list[Document]: ...
    def exists(self, doc_id: str) -> bool: ...

    # Entries (Input)
    def save_entry(self, entry: Entry) -> None: ...
    def get_entry(self, entry_id: str) -> Entry | None: ...
    def get_entries_by_source(self, source_id: str) -> builtins.list[Entry]: ...


@runtime_checkable
class MediaStore(Protocol):
    def upload(self, data: bytes, mime_type: str) -> Link:
        """Uploads binary data and returns a Link with href/type/length.

        href can be a local path, HTTP URL, or custom scheme (e.g. s3://...).
        """
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Manages vector embeddings for Documents (RAG)."""

    def add(self, docs: list[Document]) -> None:
        """Embeds and indexes documents."""
        ...

    def search(self, query: str, k: int = 5, filter_type: DocumentType | None = None) -> list[Document]:
        """Semantic search."""
        ...


@runtime_checkable
class LLMModel(Protocol):
    """Synchronous Interface for LLM/Agent operations.

    Wraps pydantic-ai.Agent or other engines.
    """

    def generate(self, prompt: str, system_prompt: str | None = None, tools: list[Any] | None = None) -> str:
        """Generates text completion synchronously."""
        ...

    def embed(self, text: str) -> list[float]:
        """Generates vector embedding synchronously."""
        ...


@runtime_checkable
class Agent(Protocol):
    """Cognitive Agent that processes Entries into Documents."""

    def process(self, entries: list[Entry]) -> list[Document]:
        """Processes a batch of entries (e.g. a window of chat messages) and produces derived Documents.

        Example: Post, Journal entry.
        """
        ...


@runtime_checkable
class UrlConvention(Protocol):
    """Pure logical protocol for determining URL paths for Documents.

    Separate from I/O.
    """

    def resolve(self, doc: Document) -> str:
        """Returns the logical URL path (e.g., 'posts/2023/my-post')."""
        ...


@runtime_checkable
class OutputSink(Protocol):
    """Final destination for published Documents (e.g. Markdown files)."""

    def publish(self, feed: Feed) -> None:
        """Writes feed/documents to disk/storage."""
        ...
