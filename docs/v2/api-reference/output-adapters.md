# Output Adapters Reference

Output adapters transform generated documents into publishable formats (MkDocs sites, static files, databases).

## Overview

Output adapters provide:

- **MkDocs Adapter**: Generate Material for MkDocs sites from documents
- **Database Sink**: Persist documents to DuckDB storage
- **Base Adapter Interface**: Abstract interface for custom output adapters
- **URL Conventions**: Standard URL generation and routing
- **Markdown Generation**: Convert documents to formatted markdown
- **Site Generation**: Complete site scaffolding and configuration

All output adapters implement a common interface for consistency.

## Base Adapter Interface

### OutputAdapter

Abstract base class for all output adapters.

::: egregora.output_adapters.base
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## MkDocs Output Adapter

The primary output adapter for generating MkDocs-based static sites.

### MkDocs Adapter

Main adapter for MkDocs site generation.

::: egregora.output_adapters.mkdocs.adapter
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

### Site Generator

Orchestrates complete site generation.

::: egregora.output_adapters.mkdocs.site_generator
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

### Scaffolding

Creates MkDocs site structure and configuration.

::: egregora.output_adapters.mkdocs.scaffolding
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

### Markdown Generation

Converts documents to formatted markdown.

::: egregora.output_adapters.mkdocs.markdown
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

### Path Management

Manages file paths and directory structure for MkDocs sites.

::: egregora.output_adapters.mkdocs.paths
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Database Sink

### DB Sink Adapter

Persists documents to DuckDB for querying and analysis.

::: egregora.output_adapters.db_sink
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## URL Conventions

Standard URL generation and routing for content.

::: egregora.output_adapters.conventions
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Usage Examples

### Using the MkDocs Adapter

```python
from egregora.output_adapters.mkdocs import MkDocsOutputAdapter
from egregora.data_primitives.document import Document, DocumentType
from pathlib import Path

# Create adapter
adapter = MkDocsOutputAdapter(
    site_root=Path("./my-blog"),
    config=egregora_config,
)

# Write single document
post = Document(
    content="# My Post\n\nPost content here...",
    type=DocumentType.POST,
    metadata={
        "title": "My Post",
        "date": "2025-01-15",
        "slug": "my-post",
    }
)

adapter.write_document(post)

# Write multiple documents
documents = [post1, post2, post3]
adapter.write_documents(documents)
```

### Generating a Complete Site

```python
from egregora.output_adapters.mkdocs.site_generator import generate_site

# Generate complete MkDocs site
await generate_site(
    site_root=Path("./my-blog"),
    documents=all_documents,
    config=egregora_config,
)

# This creates:
# - docs/ directory with markdown files
# - mkdocs.yml configuration
# - Media files in docs/media/
# - Navigation structure
# - Theme customizations
```

### Creating Site Scaffolding

```python
from egregora.output_adapters.mkdocs.scaffolding import create_mkdocs_scaffolding

# Create initial site structure
create_mkdocs_scaffolding(
    site_root=Path("./my-blog"),
    site_name="My Personal Blog",
    author="Alice",
)

# Creates:
# - mkdocs.yml
# - docs/index.md
# - docs/about.md
# - docs/stylesheets/
# - docs/javascripts/
```

### Using Path Management

```python
from egregora.output_adapters.mkdocs.paths import MkDocsPaths

# Create path manager
paths = MkDocsPaths(site_root=Path("./my-blog"))

# Get standard paths
print(paths.docs_dir)        # ./my-blog/docs
print(paths.posts_dir)       # ./my-blog/docs/posts
print(paths.media_dir)       # ./my-blog/docs/media
print(paths.config_file)     # ./my-blog/mkdocs.yml

# Get post path
post_path = paths.get_post_path(slug="my-post")
# ./my-blog/docs/posts/my-post.md

# Get media path
media_path = paths.get_media_path(filename="photo.jpg")
# ./my-blog/docs/media/photo.jpg
```

### Converting to Markdown

```python
from egregora.output_adapters.mkdocs.markdown import document_to_markdown

# Convert document to markdown with frontmatter
markdown = document_to_markdown(
    document=post,
    include_frontmatter=True,
)

# Result:
# ---
# title: My Post
# date: 2025-01-15
# slug: my-post
# ---
#
# # My Post
#
# Post content here...
```

### Using URL Conventions

```python
from egregora.output_adapters.conventions import (
    generate_post_url,
    generate_media_url,
    generate_profile_url,
)

# Generate post URL
post_url = generate_post_url(slug="my-post")
# /posts/my-post/

# Generate media URL
media_url = generate_media_url(filename="photo.jpg")
# /media/photo.jpg

# Generate profile URL
profile_url = generate_profile_url(author_id="alice")
# /profiles/alice/
```

### Using Database Sink

```python
from egregora.output_adapters.db_sink import DatabaseSink

# Create database sink
sink = DatabaseSink(
    db_path=Path("./my-blog/pipeline.duckdb")
)

# Write documents to database
sink.write_documents(documents)

# Documents are stored in 'documents' table
# Can be queried later for analysis
```

### Creating a Custom Output Adapter

```python
from egregora.output_adapters.base import OutputAdapter
from egregora.data_primitives.document import Document
from pathlib import Path

class CustomOutputAdapter(OutputAdapter):
    """Custom output adapter for specific format."""

    def __init__(self, output_path: Path):
        self.output_path = output_path

    def write_document(self, document: Document) -> None:
        """Write single document."""
        # Custom write logic
        file_path = self.output_path / f"{document.metadata['slug']}.txt"
        file_path.write_text(document.content)

    def write_documents(self, documents: list[Document]) -> None:
        """Write multiple documents."""
        for doc in documents:
            self.write_document(doc)

    def finalize(self) -> None:
        """Finalize output (e.g., generate index)."""
        # Create index or manifest
        pass

# Use custom adapter
adapter = CustomOutputAdapter(Path("./output"))
adapter.write_documents(documents)
adapter.finalize()
```

## Site Structure

MkDocs adapter generates this structure:

```
my-blog/
├── mkdocs.yml              # MkDocs configuration
├── docs/
│   ├── index.md            # Home page
│   ├── about.md            # About page
│   ├── posts/              # Blog posts
│   │   ├── 2025-01-15-my-post.md
│   │   ├── 2025-01-14-another-post.md
│   │   └── index.md        # Posts index
│   ├── profiles/           # Author profiles
│   │   ├── alice.md
│   │   ├── bob.md
│   │   └── index.md
│   ├── media/              # Media files
│   │   ├── photo1.jpg
│   │   └── photo2.png
│   ├── stylesheets/        # Custom CSS
│   │   └── extra.css
│   └── javascripts/        # Custom JS
│       └── extra.js
├── pipeline.duckdb         # Pipeline database
└── .egregora/              # Pipeline state
    └── checkpoint.json
```

## MkDocs Configuration

The adapter generates `mkdocs.yml` with:

```yaml
site_name: My Personal Blog
theme:
  name: material
  palette:
    - scheme: default
      primary: teal
      accent: amber
  features:
    - navigation.instant
    - navigation.tracking
    - search.suggest

plugins:
  - search
  - tags

nav:
  - Home: index.md
  - Posts: posts/
  - About: about.md
```

## Markdown Frontmatter

Generated markdown includes YAML frontmatter:

```markdown
---
title: My Post
date: 2025-01-15
slug: my-post
tags:
  - conversation
  - whatsapp
authors:
  - alice
  - bob
elo_rating: 1532
---

# My Post

Post content here...
```

## URL Structure

Standard URL patterns:

| Content Type | URL Pattern | Example |
|--------------|-------------|---------|
| Post | `/posts/{slug}/` | `/posts/my-post/` |
| Profile | `/profiles/{author_id}/` | `/profiles/alice/` |
| Media | `/media/{filename}` | `/media/photo.jpg` |
| Tag | `/tags/{tag}/` | `/tags/conversation/` |
| Archive | `/archive/{year}/{month}/` | `/archive/2025/01/` |

## Performance Optimization

### Incremental Updates

Only regenerate changed files:

```python
# Check if document changed
if document.document_id in existing_documents:
    if documents_match(document, existing):
        continue  # Skip unchanged

# Write only new/changed documents
adapter.write_document(document)
```

### Batch Writing

Write documents in batches for efficiency:

```python
# Batch write (more efficient)
adapter.write_documents(documents)

# Single writes (less efficient)
for doc in documents:
    adapter.write_document(doc)
```

### Media Optimization

Optimize media files during output:

```python
from egregora.output_adapters.mkdocs import optimize_media

# Resize and compress images
optimized_media = optimize_media(
    media_files=media_documents,
    max_width=1200,
    quality=85,
)
```

## Error Handling

Output operations raise specific exceptions:

```python
from egregora.output_adapters.exceptions import (
    OutputWriteError,
    InvalidDocumentError,
    PathCreationError,
)

try:
    adapter.write_document(document)
except OutputWriteError as e:
    print(f"Failed to write: {e}")
except InvalidDocumentError as e:
    print(f"Invalid document: {e}")
except PathCreationError as e:
    print(f"Failed to create path: {e}")
```

## Configuration

Output adapter behavior is configured via TOML:

```toml
[output]
adapter = "mkdocs"
site_root = "./my-blog"

[output.mkdocs]
theme = "material"
navigation_style = "sections"
enable_search = true

[output.media]
optimize_images = true
max_image_width = 1200
image_quality = 85
```

See [Configuration Reference](../getting-started/configuration.md) for full details.
