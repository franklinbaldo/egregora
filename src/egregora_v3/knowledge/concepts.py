"""Concept models for the Living Grimoire (Project Alexandria).

This module defines the data structures for the 'Concept Miner' engine, which extracts
semantic entities (People, Places, Events, Terms) from the temporal stream and
synthesizes them into a Wiki-like knowledge graph.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from egregora_v3.core.types import Document, DocumentType, DocumentStatus, InReplyTo


class ConceptType(str, Enum):
    """The category of the concept."""
    PERSON = "person"      # e.g., "Gary"
    PLACE = "place"        # e.g., "The Old Cabin"
    EVENT = "event"        # e.g., "The Noodle Incident"
    ARTIFACT = "artifact"  # e.g., "The Golden Spoon"
    TERM = "term"          # e.g., "Glamping"
    MEME = "meme"          # e.g., "Wednesday Frog"
    OTHER = "other"


class ConceptRelation(BaseModel):
    """A directed relationship between concepts."""
    target_slug: str
    relation_type: str  # e.g., "participated_in", "located_at", "caused"
    description: str | None = None


class ConceptExtraction(BaseModel):
    """The raw output from the Concept Miner agent for a single text chunk."""
    name: str
    type: ConceptType
    description: str
    related_slugs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class WikiPage(Document):
    """A synthesized Wiki Page representing a Concept."""

    # Enforce type
    doc_type: Literal[DocumentType.CONCEPT] = DocumentType.CONCEPT

    concept_type: ConceptType
    aliases: list[str] = Field(default_factory=list)
    relations: list[ConceptRelation] = Field(default_factory=list)

    # Backlinks to source Entries (Evidence)
    evidence_refs: list[str] = Field(default_factory=list)

    @classmethod
    def create_concept(
        cls,
        name: str,
        content: str,
        concept_type: ConceptType,
        evidence_refs: list[str],
        *,
        aliases: list[str] | None = None,
        relations: list[ConceptRelation] | None = None,
        status: DocumentStatus = DocumentStatus.PUBLISHED,
    ) -> "WikiPage":
        """Factory for creating a WikiPage."""
        # Call Document.create explicitly to get a base Document instance
        # This avoids validation errors because Document.create() calls cls()
        # and WikiPage requires extra fields not known to Document.create
        doc = Document.create(
            content=content,
            doc_type=DocumentType.CONCEPT,
            title=name,
            status=status,
            slug=name,  # Use name as semantic ID
        )
        # Use simple dictionary unpacking to ensure all fields are passed
        data = doc.model_dump()
        data.update({
            "concept_type": concept_type,
            "aliases": aliases or [],
            "relations": relations or [],
            "evidence_refs": evidence_refs,
            "doc_type": DocumentType.CONCEPT,  # Ensure correct type
        })
        return cls(**data)
