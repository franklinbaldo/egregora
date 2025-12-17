from datetime import datetime
from egregora.data_primitives.document import Document, DocumentType


def _get_title_fallback(doc_type: DocumentType) -> str:
    """Provides a sensible default title based on the document type."""
    return f"Untitled {doc_type.value.capitalize()}"


def ensure_minimum_metadata(document: Document) -> Document:
    """
    Ensures a document has the minimum required metadata for publishing.
    This function adds default values for missing keys to ensure consistency
    across all document types, which is essential for features like RSS feeds,
    sitemaps, and theme features in the MkDocs output.
    Args:
        document: The input document.
    Returns:
        A new document instance with normalized metadata.
    """
    meta = document.metadata.copy()  # Work on a copy

    source_info = {"adapter": "unknown"}
    if document.source_window:
        source_info["window_label"] = document.source_window

    # Define defaults and fallbacks. The order doesn't matter here.
    defaults = {
        "title": _get_title_fallback(document.type),
        "slug": document.slug,
        "date": document.created_at.isoformat(),
        "summary": "",
        "tags": [],
        "categories": [],
        "authors": [],
        "draft": False,
        "type": document.type.value,
        "doc_id": document.document_id,
        "source": source_info,
    }

    # Apply defaults for any key that is missing or has a value of None.
    for key, default_value in defaults.items():
        if meta.get(key) is None:
            meta[key] = default_value

    # 'updated' defaults to the value of 'date' if it's not set.
    if meta.get("updated") is None:
        meta["updated"] = meta["date"]

    # Ensure source is a dict and has the adapter key
    if not isinstance(meta.get("source"), dict):
        meta["source"] = source_info  # Fallback to default source info
    elif "adapter" not in meta["source"]:
        meta["source"]["adapter"] = "unknown"

    # The dataclass is frozen, so we create a new document with the updated metadata.
    return document.with_metadata(**meta)
