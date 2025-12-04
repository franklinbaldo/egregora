from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from egregora_v3.core.ports import DocumentRepository


class ContentLibrary(BaseModel):
    """
    Facade for accessing typed document repositories.
    Replacing the AtomPub-style 'Service' discovery.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Typed and explicit repositories
    posts: DocumentRepository
    media: DocumentRepository
    journal: DocumentRepository
    profiles: DocumentRepository

    # Global settings/metadata
    settings: dict[str, Any] = Field(default_factory=dict)
