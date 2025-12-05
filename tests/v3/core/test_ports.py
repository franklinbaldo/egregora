import builtins
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from egregora_v3.core.ports import (
    Agent,
    DocumentRepository,
    InputAdapter,
    OutputSink,
)
from egregora_v3.core.types import Document, DocumentType, Entry, Feed


class MockInputAdapter(InputAdapter):
    def parse(self, source: Path) -> Iterator[Entry]:
        yield Entry(id="1", updated=datetime.now(UTC), title="test", content="content")

class MockRepo(DocumentRepository):
    # Updated signature to return Document
    def save(self, doc: Document) -> Document: return doc
    def get(self, doc_id: str) -> Document | None: return None
    # Updated signature to list by kwargs
    def list(self, *, doc_type: DocumentType | None = None) -> list[Document]: return []
    def exists(self, doc_id: str) -> bool: return False

    def save_entry(self, item: Entry) -> None: pass
    def get_entry(self, item_id: str) -> Entry | None: return None
    def get_entries_by_source(self, source_id: str) -> builtins.list[Entry]: return []

class MockAgent(Agent):
    def process(self, entries: list[Entry]) -> list[Document]:
        return [Document.create(content="generated", doc_type=DocumentType.POST, title="Gen")]

class MockOutputSink(OutputSink):
    def publish(self, feed: Feed) -> None:
        pass

def test_ports_structural_compatibility():
    # This test primarily ensures that the Mocks implement the Protocols correctly
    # If Mypy was running, it would check this. Runtime check via instantiation is basic.
    repo = MockRepo()
    assert isinstance(repo, DocumentRepository)

    adapter = MockInputAdapter()
    assert isinstance(adapter, InputAdapter)

    agent = MockAgent()
    assert isinstance(agent, Agent)

    sink = MockOutputSink()
    assert isinstance(sink, OutputSink)
