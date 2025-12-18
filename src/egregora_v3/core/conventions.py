from datetime import datetime
from pathlib import Path

from egregora_v3.core.ports import UrlConvention
from egregora_v3.core.types import Document, DocumentType


class DateSlugConvention(UrlConvention):
    """Generates paths based on date and slug: 'YYYY/MM/DD/slug'.

    Example:
        Document(date=2024-03-15, slug="hello-world") -> "posts/2024/03/15/hello-world"
    """

    def resolve(self, doc: Document) -> str:
        """Resolve document to a logical path string."""
        if not doc.slug:
            # Fallback for documents without slug (e.g. using ID)
            return f"orphans/{doc.id}"

        # Determine base directory by type
        base_dir = self._get_base_dir(doc.doc_type)

        # Extract date components
        # Prefer 'date' metadata, fallback to 'published', then 'updated'
        date_obj = self._extract_date(doc)

        # Build path
        path_parts = [base_dir]
        if date_obj:
            path_parts.extend([
                f"{date_obj.year:04d}",
                f"{date_obj.month:02d}",
                f"{date_obj.day:02d}",
            ])

        path_parts.append(doc.slug)

        return "/".join(path_parts)

    def _get_base_dir(self, doc_type: DocumentType) -> str:
        match doc_type:
            case DocumentType.POST:
                return "posts"
            case DocumentType.MEDIA:
                return "media"
            case DocumentType.PROFILE:
                return "profiles"
            case DocumentType.NOTE:
                return "notes"
            case _:
                return f"{doc_type.value}s"

    def _extract_date(self, doc: Document) -> datetime | None:
        # Check metadata first
        if "date" in doc.internal_metadata:
            val = doc.internal_metadata["date"]
            if isinstance(val, datetime):
                return val
            # Handle string dates? Maybe later.

        if doc.published:
            return doc.published

        return doc.updated
