# Data Model: Atom Protocol

Egregora Pure standardizes on the **Atom Syndication Format (RFC 4287)** for internal data representation.

## The `Entry`

The base unit of data is the `Entry`. It represents a single discrete item of content (e.g., a chat message, a blog post, a media item).

```python
class Entry(BaseModel):
    id: str  # Unique identifier (UUID or URI)
    title: str
    updated: datetime
    published: datetime | None
    content: Content | None
    links: List[Link]
    authors: List[Person]
    categories: List[Category]
```

## The `Document`

A `Document` is an `Entry` that is ready for publication or has been processed by the pipeline. It extends `Entry` with additional system metadata.

## Feed

A `Feed` is a collection of `Entry` objects, typically representing a stream of content.
