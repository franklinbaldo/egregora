"""Core Data Types for Egregora V3."""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from xml.etree.ElementTree import Element, register_namespace, SubElement, tostring

from markdown_it import MarkdownIt
from pydantic import BaseModel, Field, model_validator
import jinja2

from egregora_v3.core.utils import slugify

# --- XML Configuration ---
try:
    register_namespace("", "http://www.w3.org/2005/Atom")
    register_namespace("thr", "http://purl.org/syndication/thread/1.0")
except Exception:
    pass

# --- Jinja2 Environment ---
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("src/egregora_v3/infra/sinks/templates/"),
    autoescape=jinja2.select_autoescape(['html', 'xml']),
    trim_blocks=True,
    lstrip_blocks=True,
)

def format_iso_utc(dt: datetime) -> str:
    return dt.isoformat()

_jinja_env.filters['iso_utc'] = format_iso_utc

# --- Atom Core Domain ---
class Link(BaseModel):
    href: str
    rel: str | None = None
    type: str | None = None
    hreflang: str | None = None
    title: str | None = None
    length: int | None = None

class Author(BaseModel):
    name: str
    email: str | None = None
    uri: str | None = None

class Category(BaseModel):
    term: str
    scheme: str | None = None
    label: str | None = None

class Source(BaseModel):
    id: str | None = None
    title: str | None = None
    updated: datetime | None = None
    links: list[Link] = Field(default_factory=list)

class InReplyTo(BaseModel):
    ref: str
    href: str | None = None
    type: str | None = None

class Entry(BaseModel):
    id: str
    title: str
    updated: datetime
    published: datetime | None = None
    links: list[Link] = Field(default_factory=list)
    authors: list[Author] = Field(default_factory=list)
    contributors: list[Author] = Field(default_factory=list)
    categories: list[Category] = Field(default_factory=list)
    summary: str | None = None
    content: str | None = None
    content_type: str | None = None
    source: Source | None = None
    in_reply_to: InReplyTo | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)
    internal_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_document(self) -> bool:
        return False

    @property
    def has_enclosure(self) -> bool:
        if not self.links:
            return False
        return any(link.rel == "enclosure" for link in self.links)

# --- Application Domain ---
class DocumentType(str, Enum):
    RECAP = "recap"
    NOTE = "note"
    PLAN = "plan"
    POST = "post"
    MEDIA = "media"
    PROFILE = "profile"
    ENRICHMENT = "enrichment"
    CONCEPT = "concept"

class DocumentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class Document(Entry):
    doc_type: DocumentType
    status: DocumentStatus = DocumentStatus.DRAFT
    searchable: bool = True
    url_path: str | None = None

    @property
    def is_document(self) -> bool:
        return True

    @property
    def slug(self) -> str | None:
        return self.internal_metadata.get("slug")

    @model_validator(mode="before")
    @classmethod
    def _generate_identity_from_title(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("id"):
                return data
            internal_metadata = data.get("internal_metadata", {})
            final_slug = data.get("slug")
            if not final_slug:
                title = data.get("title", "")
                if not title:
                    return data
                final_slug = slugify(title.strip())
            if not final_slug:
                msg = "Document must have a slug or a title to generate one."
                raise ValueError(msg)
            data["id"] = final_slug
            internal_metadata["slug"] = final_slug
            data["internal_metadata"] = internal_metadata
            if "updated" not in data:
                data["updated"] = datetime.now(UTC)
        return data

class Feed(BaseModel):
    id: str
    title: str
    updated: datetime
    entries: list[Entry] = Field(default_factory=list)
    authors: list[Author] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)

    def get_published_documents(self) -> list[Document]:
        """Return a filtered list of published documents from the feed entries."""
        return [
            entry
            for entry in self.entries
            if isinstance(entry, Document) and entry.status == DocumentStatus.PUBLISHED
        ]

    def to_xml(self) -> str:
        md = MarkdownIt()
        template = _jinja_env.get_template("atom.xml.jinja")

        feed_for_render = self.model_copy(deep=True)

        for entry in feed_for_render.entries:
            if entry.content:
                entry.content = md.render(entry.content).strip()

        return template.render(feed=feed_for_render).strip()

def documents_to_feed(
    docs: list[Document],
    feed_id: str,
    title: str,
    authors: list[Author] | None = None,
) -> Feed:
    if not docs:
        updated = datetime.now(UTC)
    else:
        updated = max(doc.updated for doc in docs)
    sorted_docs = sorted(docs, key=lambda d: d.updated, reverse=True)
    return Feed(
        id=feed_id,
        title=title,
        updated=updated,
        authors=authors or [],
        entries=sorted_docs,
    )
