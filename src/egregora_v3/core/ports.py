from typing import Protocol, Iterator, List, Optional, Any, Dict, runtime_checkable
from pathlib import Path
from uuid import UUID

from egregora_v3.core.types import Document, Message, DocumentType

@runtime_checkable
class InputAdapter(Protocol):
    """
    Parses a source input into a stream of Messages.
    """
    def parse(self, source: Path) -> Iterator[Message]:
        ...

@runtime_checkable
class DocumentRepository(Protocol):
    """
    Persists and retrieves Document primitives.
    """
    def save(self, doc: Document) -> None:
        ...

    def get(self, doc_id: UUID) -> Optional[Document]:
        ...

    def list_by_type(self, doc_type: DocumentType) -> List[Document]:
        ...

    def exists(self, doc_id: UUID) -> bool:
        ...

@runtime_checkable
class VectorStore(Protocol):
    """
    Manages vector embeddings for Documents (RAG).
    """
    def add(self, docs: List[Document]) -> None:
        """Embeds and indexes documents."""
        ...

    def search(self, query: str, k: int = 5, filter_type: Optional[DocumentType] = None) -> List[Document]:
        """Semantic search."""
        ...

@runtime_checkable
class LLMClient(Protocol):
    """
    Synchronous Interface for LLM operations.
    """
    def generate(self, prompt: str, system_prompt: Optional[str] = None, tools: Optional[List[Any]] = None) -> str:
        """Generates text completion."""
        ...

    def embed(self, text: str) -> List[float]:
        """Generates vector embedding."""
        ...

@runtime_checkable
class OutputSink(Protocol):
    """
    Final destination for published Documents (e.g. Markdown files).
    """
    def persist(self, doc: Document) -> Path:
        """Writes document to disk/storage and returns the location."""
        ...
