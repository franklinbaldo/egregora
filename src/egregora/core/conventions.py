from datetime import datetime

from egregora.core.ports import UrlConvention
from egregora.core.types import Document, DocumentType


class DateSlugConvention(UrlConvention):
    """Generates paths based on date and slug: 'YYYY/MM/DD/slug'.

    Example:
        Document(published=2024-03-15, slug="hello-world") -> "posts/2024/03/15/hello-world"
    """

    # Data over logic: Use a map for base directories
    _BASE_DIR_MAP = {
        DocumentType.POST: "posts",
        DocumentType.MEDIA: "media",
        DocumentType.PROFILE: "profiles",
        DocumentType.NOTE: "notes",
    }

    def resolve(self, doc: Document) -> str:
        """Resolve document to a logical path string."""
        if not doc.slug:
            # Fallback for documents without slug (e.g. using ID)
            return f"orphans/{doc.id}"

        # Determine base directory by type
        base_dir = self._get_base_dir(doc.doc_type)

        # Extract date components (explicit path)
        date_obj = self._extract_date(doc)

        # Build path
        path_parts = [
            base_dir,
            f"{date_obj.year:04d}",
            f"{date_obj.month:02d}",
            f"{date_obj.day:02d}",
            doc.slug,
        ]

        return "/".join(path_parts)

    def _get_base_dir(self, doc_type: DocumentType) -> str:
        """Get base directory from the map, with a fallback."""
        return self._BASE_DIR_MAP.get(doc_type, f"{doc_type.value}s")

    def _extract_date(self, doc: Document) -> datetime:
        """Extract date from standard Atom fields.

        One good path: Prefer `published` date, but always fall back to `updated`.
        This avoids complex, optional logic based on internal metadata.
        """
        return doc.published or doc.updated
