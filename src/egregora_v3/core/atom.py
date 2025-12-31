"""Atom feed serialization."""

from xml.etree.ElementTree import Element, register_namespace, SubElement, tostring
from egregora_v3.core.types import Feed, Entry, Link, Author, Category, InReplyTo, Document


def feed_to_xml_string(feed: Feed) -> str:
    """Serialize a Feed object to an Atom XML string."""
    register_namespace("", "http://www.w3.org/2005/Atom")
    register_namespace("thr", "http://purl.org/syndication/thread/1.0")

    root = Element("feed", attrib={"xmlns": "http://www.w3.org/2005/Atom"})
    SubElement(root, "id").text = feed.id
    SubElement(root, "title").text = feed.title
    SubElement(root, "updated").text = feed.updated.isoformat()

    for author in feed.authors:
        author_el = SubElement(root, "author")
        SubElement(author_el, "name").text = author.name
        if author.email:
            SubElement(author_el, "email").text = author.email
        if author.uri:
            SubElement(author_el, "uri").text = author.uri

    for link in feed.links:
        SubElement(root, "link", attrib=_pydantic_to_dict(link))

    for entry in feed.entries:
        entry_el = SubElement(root, "entry")
        SubElement(entry_el, "id").text = entry.id
        SubElement(entry_el, "title").text = entry.title
        SubElement(entry_el, "updated").text = entry.updated.isoformat()

        if entry.published:
            SubElement(entry_el, "published").text = entry.published.isoformat()

        for author in entry.authors:
            author_el = SubElement(entry_el, "author")
            SubElement(author_el, "name").text = author.name
            if author.email:
                SubElement(author_el, "email").text = author.email
            if author.uri:
                SubElement(author_el, "uri").text = author.uri

        for link in entry.links:
            SubElement(entry_el, "link", attrib=_pydantic_to_dict(link))

        for category in entry.categories:
            SubElement(entry_el, "category", attrib=_pydantic_to_dict(category))

        if isinstance(entry, Document):
            SubElement(
                entry_el,
                "category",
                attrib={
                    "term": entry.doc_type.value,
                    "scheme": "https://egregora.app/schema#doc_type",
                },
            )
            SubElement(
                entry_el,
                "category",
                attrib={
                    "term": entry.status.value,
                    "scheme": "https://egregora.app/schema#status",
                },
            )

        if entry.summary:
            SubElement(entry_el, "summary").text = entry.summary

        if entry.content:
            content_el = SubElement(entry_el, "content")
            content_el.text = entry.content
            content_type = entry.content_type
            if content_type == "text/markdown":
                content_type = "text"
            if content_type:
                content_el.set("type", content_type)

        if entry.in_reply_to:
            SubElement(
                entry_el,
                "{http://purl.org/syndication/thread/1.0}in-reply-to",
                attrib=_pydantic_to_dict(entry.in_reply_to),
            )

    return '<?xml version=\'1.0\' encoding=\'UTF-8\'?>' + tostring(root, encoding="unicode")


def _pydantic_to_dict(model) -> dict[str, str]:
    """Convert a Pydantic model to a dict of strings for XML attributes."""
    return {k: str(v) for k, v in model.model_dump().items() if v is not None}
