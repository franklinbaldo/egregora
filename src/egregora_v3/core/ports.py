from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from egregora_v3.core.types import Document, DocumentType, FeedItem


@runtime_checkable
class InputAdapter(Protocol):
    """Parses a source input into a stream of FeedItems."""

    def parse(self, source: Path) -> Iterator[FeedItem]:
        ...


@runtime_checkable
class DocumentRepository(Protocol):
    """Persists and retrieves Document and FeedItem primitives."""

    # Documents
    def save(self, doc: Document) -> None: ...
    def get(self, doc_id: UUID) -> Document | None: ...
    def list_by_type(self, doc_type: DocumentType) -> list[Document]: ...
    def exists(self, doc_id: UUID) -> bool: ...

    # FeedItems (Messages)
    def save_item(self, item: FeedItem) -> None: ...
    def get_item(self, item_id: UUID) -> FeedItem | None: ...
    def get_items_by_source(self, source: str) -> list[FeedItem]: ...


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
    """Cognitive Agent that processes FeedItems into Documents."""

    def process(self, items: list[FeedItem]) -> list[Document]:
        """Processes a batch of items (e.g. a window of chat messages) and produces derived Documents.

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

    def persist(self, doc: Document) -> Path:
        """Writes document to disk/storage and returns the location."""
        ...
