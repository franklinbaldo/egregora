import hashlib
import uuid
from enum import Enum, auto
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict

class DocumentType(str, Enum):
    POST = "post"
    PROFILE = "profile"
    JOURNAL = "journal"
    ENRICHMENT = "enrichment"
    MEDIA = "media"

class UUIDNamespace(BaseModel):
    """Namespace for deterministic UUID generation."""
    # Using a random UUID as the base namespace for V3
    base: uuid.UUID = uuid.UUID("a1b2c3d4-e5f6-7890-1234-567890abcdef")

    def generate(self, *args: str) -> uuid.UUID:
        """Generates a deterministic UUID based on input strings."""
        content = ":".join(args)
        return uuid.uuid5(self.base, content)

class Message(BaseModel):
    """
    Represents a single message in the chat stream.
    Immutable primitive.
    """
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(..., description="Unique ID of the message")
    timestamp: datetime = Field(..., description="Timestamp of the message")
    author: str = Field(..., description="Author identifier (e.g., phone number)")
    content: str = Field(..., description="Text content of the message")
    attachments: List[str] = Field(default_factory=list, description="List of attachment paths")

    @property
    def word_count(self) -> int:
        return len(self.content.split())

class Document(BaseModel):
    """
    Unified Document primitive.
    Used for Posts, Profiles, Journals, Enrichments, and Media.
    """
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(..., description="Unique ID of the document")
    type: DocumentType = Field(..., description="Type of the document")
    content: str = Field(..., description="Main content (Markdown, JSON, etc.)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata key-values")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation time")

    @classmethod
    def create(cls,
               content: str,
               doc_type: DocumentType,
               metadata: Optional[Dict[str, Any]] = None,
               id_override: Optional[uuid.UUID] = None) -> "Document":
        """
        Factory method to create a Document.
        If id_override is not provided, generates a content-addressed ID.
        """
        if metadata is None:
            metadata = {}

        if id_override:
            doc_id = id_override
        else:
            # Content-addressed ID based on content + type
            hasher = hashlib.sha256()
            hasher.update(content.encode('utf-8'))
            hasher.update(doc_type.value.encode('utf-8'))
            # We use the hash to generate a UUID
            doc_id = uuid.uuid5(uuid.NAMESPACE_DNS, hasher.hexdigest())

        return cls(
            id=doc_id,
            type=doc_type,
            content=content,
            metadata=metadata,
            created_at=datetime.now(timezone.utc)
        )
