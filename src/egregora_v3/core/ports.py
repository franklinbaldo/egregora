from collections.abc import Iterator
from pathlib import Path
from typing import Any, List, Protocol, runtime_checkable

from egregora_v3.core.types import Document, DocumentType, Entry, Feed


@runtime_checkable
class InputAdapter(Protocol):
    """Parses a source input into a stream of Entries."""

    def parse(self, source: Path) -> Iterator[Entry]:
        ...


@runtime_checkable
class DocumentRepository(Protocol):
    """Persists and retrieves Document and Entry primitives."""

    # Core Persistence
    def save(self, doc: Document) -> None:
        """Upsert a document."""
        ...

    def get(self, doc_id: str) -> Document | None:
        """Retrieve by ID."""
        ...

    def list_collection(self, collection_name: str) -> Iterator[Document]:
        """List all documents in a specific collection."""
        ...

    def get_high_water_mark(self, collection_name: str) -> Any | None:
        """Get the maximum 'updated' timestamp for resumption."""
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Manages vector embeddings for Documents (RAG)."""

    def add(self, docs: List[Document]) -> None:
        """Embeds and indexes documents."""
        ...

    def search(self, query: str, k: int = 5, filter_type: DocumentType | None = None) -> List[Document]:
        """Semantic search."""
        ...


@runtime_checkable
class LLMModel(Protocol):
    """Synchronous Interface for LLM/Agent operations.

    Wraps pydantic-ai.Agent or other engines.
    """

    def generate(self, prompt: str, system_prompt: str | None = None, tools: List[Any] | None = None) -> str:
        """Generates text completion synchronously."""
        ...

    def embed(self, text: str) -> List[float]:
        """Generates vector embedding synchronously."""
        ...


@runtime_checkable
class Agent(Protocol):
    """Cognitive Agent that processes Entries into Documents."""

    def process(self, entries: List[Entry]) -> List[Document]:
        """Processes a batch of entries (e.g. a window of chat messages) and produces derived Documents.

        Example: Post, Journal entry.
        """
        ...
