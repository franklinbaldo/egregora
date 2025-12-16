# ADR-001: Media Path Convention

## Status
Accepted

## Context
Media files (images, videos) uploaded by users need a consistent storage location in the MkDocs output structure. There was confusion about whether media should be:
- `/docs/media/` (sibling to posts)
- `/docs/posts/media/` (inside posts)

The URL routing and filesystem paths must be consistent.

## Decision
We adopt **`docs/post/media/`** as the single global root for assets.

**URL**: `/post/media/{filename}`
**Filesystem**: `docs/post/media/{filename}`

### Configuration
```python
# conventions.py
media_prefix: str = "post/media"

# paths.py
media_dir = docs_dir / "post" / "media"
```

### Rationale
1. **Standardization**: Singular "post" directory for consistent media assets.
2. **Simplification**: Unified path resolution across the codebase.
3. **MkDocs compatibility**: Explicit asset root.

## Consequences

### Easier
- Consistent path resolution.
- Clear separation of media assets.

### Harder
- Migration of existing paths required.

## Related
- ADR-002: Profile Path Convention
