from typing import Iterator, List, Optional, Any
from pathlib import Path
from uuid import UUID
from egregora_v3.core.ports import InputAdapter, DocumentRepository, VectorStore, LLMClient, OutputSink
from egregora_v3.core.types import Document, Message, DocumentType

def test_input_adapter_protocol():
    class MockAdapter:
        def parse(self, source: Path) -> Iterator[Message]:
            yield Message(id=UUID(int=1), timestamp=None, author="a", content="b") # type: ignore

    assert isinstance(MockAdapter(), InputAdapter)

def test_repo_protocol():
    class MockRepo:
        def save(self, doc: Document) -> None: pass
        def get(self, doc_id: UUID) -> Optional[Document]: return None
        def list_by_type(self, doc_type: DocumentType) -> List[Document]: return []
        def exists(self, doc_id: UUID) -> bool: return False

    assert isinstance(MockRepo(), DocumentRepository)

def test_vector_store_protocol():
    class MockVector:
        def add(self, docs: List[Document]) -> None: pass
        def search(self, query: str, k: int = 5, filter_type: Optional[DocumentType] = None) -> List[Document]: return []

    assert isinstance(MockVector(), VectorStore)

def test_llm_client_protocol():
    class MockLLM:
        def generate(self, prompt: str, system_prompt: Optional[str] = None, tools: Optional[List[Any]] = None) -> str: return ""
        def embed(self, text: str) -> List[float]: return []

    assert isinstance(MockLLM(), LLMClient)

def test_output_sink_protocol():
    class MockSink:
        def persist(self, doc: Document) -> Path: return Path(".")

    assert isinstance(MockSink(), OutputSink)
