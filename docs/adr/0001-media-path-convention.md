# ADR-001: Media Path Convention

## Status
Accepted

## Context
Media files (images, videos) uploaded by users need a consistent storage location in the MkDocs output structure. There was confusion about whether media should be:
- `/docs/media/` (sibling to posts)
- `/docs/posts/media/` (inside posts)

The URL routing and filesystem paths must be consistent.

## Decision
Media files go **inside** the posts directory:

**URL**: `/posts/media/{filename}`
**Filesystem**: `docs/posts/media/{filename}`

### Configuration
```python
# conventions.py
media_prefix: str = "posts/media"

# paths.py  
media_dir = posts_dir / "media"
```

### Rationale
1. **Logical grouping**: Media is primarily associated with blog posts
2. **URL clarity**: `/posts/media/image.jpg` clearly indicates it belongs to posts
3. **MkDocs compatibility**: Keeps all content under one subdirectory

## Consequences

### Easier
- Clear ownership: media belongs to posts section
- Single content root for backup/migration

### Harder
- If media needs to be shared across sections, URLs will include "posts/"

## Related
- ADR-002: Profile Path Convention
