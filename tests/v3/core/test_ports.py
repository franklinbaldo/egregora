from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from egregora_v3.core.ports import (
    Agent,
    DocumentRepository,
    InputAdapter,
    LLMModel,
    OutputSink,
    UrlConvention,
    VectorStore,
)
from egregora_v3.core.types import Document, DocumentType, FeedItem


def test_input_adapter_protocol():
    class MockAdapter:
        def parse(self, source: Path) -> Iterator[FeedItem]:
            yield FeedItem(id=UUID(int=1), timestamp=datetime.now(), source="a", content="b")

    assert isinstance(MockAdapter(), InputAdapter)

def test_repo_protocol():
    class MockRepo:
        def save(self, doc: Document) -> None: pass
        def get(self, doc_id: UUID) -> Document | None: return None
        def list_by_type(self, doc_type: DocumentType) -> list[Document]: return []
        def exists(self, doc_id: UUID) -> bool: return False

        def save_item(self, item: FeedItem) -> None: pass
        def get_item(self, item_id: UUID) -> FeedItem | None: return None
        def get_items_by_source(self, source: str) -> list[FeedItem]: return []

    assert isinstance(MockRepo(), DocumentRepository)

def test_vector_store_protocol():
    class MockVector:
        def add(self, docs: list[Document]) -> None: pass
        def search(self, query: str, k: int = 5, filter_type: DocumentType | None = None) -> list[Document]: return []

    assert isinstance(MockVector(), VectorStore)

def test_llm_model_protocol():
    class MockLLM:
        def generate(self, prompt: str, system_prompt: str | None = None, tools: list[Any] | None = None) -> str: return ""
        def embed(self, text: str) -> list[float]: return []

    assert isinstance(MockLLM(), LLMModel)

def test_agent_protocol():
    class MockAgent:
        def process(self, items: list[FeedItem]) -> list[Document]:
            return []

    assert isinstance(MockAgent(), Agent)

def test_url_convention_protocol():
    class MockConvention:
        def resolve(self, doc: Document) -> str: return "path/to/doc"

    assert isinstance(MockConvention(), UrlConvention)

def test_output_sink_protocol():
    class MockSink:
        def persist(self, doc: Document) -> Path: return Path()

    assert isinstance(MockSink(), OutputSink)
