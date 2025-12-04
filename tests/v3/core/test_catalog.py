from typing import List

from egregora_v3.core.catalog import Collection, Service, Workspace
from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import Document, DocumentType, Entry


class StubRepo(DocumentRepository):
    def save(self, doc: Document) -> Document: return doc
    def get(self, doc_id: str) -> Document | None: return None
    def list(self, *, doc_type: DocumentType | None = None) -> List[Document]: return []
    def exists(self, doc_id: str) -> bool: return False
    def save_entry(self, entry: Entry) -> None: pass
    def get_entry(self, entry_id: str) -> Entry | None: return None
    def get_entries_by_source(self, source_id: str) -> List[Entry]: return []

def test_service_catalog_find_collection():
    repo = StubRepo()

    posts_col = Collection(
        id="posts",
        title="Posts",
        accepts=[DocumentType.POST],
        repository=repo
    )

    media_col = Collection(
        id="media",
        title="Media",
        accepts=[DocumentType.MEDIA],
        repository=repo
    )

    ws = Workspace(title="Main", collections=[posts_col, media_col])
    service = Service(workspaces=[ws])

    # Test finding existing collection
    found = service.find_collection("posts")
    assert found is not None
    assert found.id == "posts"
    assert DocumentType.POST in found.accepts

    # Test finding another collection
    found_media = service.find_collection("media")
    assert found_media is not None
    assert found_media.id == "media"

    # Test missing collection
    assert service.find_collection("missing") is None

def test_collection_repository_access():
    repo = StubRepo()
    col = Collection(id="test", title="Test", accepts=[], repository=repo)

    # Ensure we can access the repo through the collection
    assert col.repository is repo
