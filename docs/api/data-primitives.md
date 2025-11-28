# Data Primitives API

The data primitives module provides the core data structures used throughout Egregora.

## Overview

All content produced by the Egregora pipeline is represented as `Document` instances. Documents use content-addressed IDs (UUID v5 of content hash) for deterministic identity and deduplication.

## Document

::: egregora.data_primitives.document.Document
    options:
      show_source: true
      show_root_heading: true
      show_category_heading: true
      members_order: source
      show_if_no_docstring: false
      heading_level: 3

## DocumentType

::: egregora.data_primitives.document.DocumentType
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3

## DocumentCollection

::: egregora.data_primitives.document.DocumentCollection
    options:
      show_source: true
      show_root_heading: true
      show_category_heading: true
      members_order: source
      show_if_no_docstring: false
      heading_level: 3

## MediaAsset

::: egregora.data_primitives.document.MediaAsset
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3

## Usage Examples

### Creating Documents

```python
from egregora.data_primitives.document import Document, DocumentType

# Create a blog post
post = Document(
    content="# My Post\n\nContent here...",
    type=DocumentType.POST,
    metadata={
        "title": "My Post",
        "date": "2025-01-10",
        "slug": "my-post",
    }
)

# Document ID is deterministic
print(post.document_id)  # UUID based on content hash
```

### Working with Collections

```python
from egregora.data_primitives.document import DocumentCollection

# Create a collection
docs = [post1, post2, profile1]
collection = DocumentCollection(
    documents=docs,
    window_label="2025-01-10"
)

# Filter by type
posts = collection.by_type(DocumentType.POST)
profiles = collection.by_type(DocumentType.PROFILE)

# Find by ID
doc = collection.find_by_id("some-uuid")
```

### Media Assets

```python
from egregora.data_primitives.document import MediaAsset, DocumentType

# Read image file
with open("photo.jpg", "rb") as f:
    image_data = f.read()

# Create media asset
media = MediaAsset(
    content=image_data,
    type=DocumentType.MEDIA,
    metadata={
        "filename": "photo.jpg",
        "mime_type": "image/jpeg",
    }
)

# Create enrichment linked to media
enrichment = Document(
    content="A sunset over the ocean",
    type=DocumentType.ENRICHMENT_MEDIA,
    metadata={"url": "media/photo.jpg"},
    parent_id=media.document_id
)
```
