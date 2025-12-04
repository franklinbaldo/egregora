from pydantic import BaseModel, ConfigDict, Field

from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import DocumentType


class Collection(BaseModel):
    """Represents a logical collection of documents (e.g. 'posts', 'journal')."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str                       # ex: "posts", "journal", "media"
    title: str                    # ex: "Blog Posts"
    accepts: list[DocumentType]   # ex: [DocumentType.POST]

    # RAG Indexing Policy
    index_in_rag: bool = True     # Whether items in this collection should be indexed

    # Backend that knows how to persist and list Documents of this collection
    repository: DocumentRepository


class Workspace(BaseModel):
    """Represents a logical workspace (e.g. 'Main Site', 'Private Journal')."""
    title: str                    # ex: "Egregora Main Site"
    collections: list[Collection] = Field(default_factory=list)


class Service(BaseModel):
    """
    Catalog of workspaces and collections available in Egregora.
    Conceptually equivalent to the AtomPub Service Document.
    """
    workspaces: list[Workspace] = Field(default_factory=list)

    def find_collection(self, collection_id: str) -> Collection | None:
        """Finds a collection by ID across all workspaces."""
        for ws in self.workspaces:
            for col in ws.collections:
                if col.id == collection_id:
                    return col
        return None
