"""Data primitive placeholders."""
from enum import Enum

class Author:
    pass

class Category:
    pass

class Document:
    pass

@dataclass(frozen=True, slots=True)
class Author:
    """Represents a content author."""
    id: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class Category:
    """Represents a content category or tag."""
    term: str


class DocumentType(Enum):
    POST = "POST"

class OutputSink:
    pass

class DocumentMetadata:
    pass

class UrlContext:
    pass

class UrlConvention:
    pass

class MediaAsset:
    pass
