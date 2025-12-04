from typing import List

from egregora_v3.core.library import ContentLibrary
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

def test_content_library_facade():
    repo_posts = StubRepo()
    repo_media = StubRepo()
    repo_journal = StubRepo()
    repo_profiles = StubRepo()

    library = ContentLibrary(
        posts=repo_posts,
        media=repo_media,
        journal=repo_journal,
        profiles=repo_profiles,
        settings={"env": "test"}
    )

    # Assert direct access
    assert library.posts is repo_posts
    assert library.media is repo_media
    assert library.settings["env"] == "test"

    # Verify type checking (static/runtime check)
    assert isinstance(library.posts, DocumentRepository)
