# ADR-001: Media Path Convention

## Status
Accepted

## Context
Media files (images, videos) uploaded by users need a consistent storage location in the MkDocs output structure. There was confusion about whether media should be:
- `/docs/media/` (sibling to posts)
- `/docs/posts/media/` (inside posts)

The URL routing and filesystem paths must be consistent.

## Decision
We adopt **`docs/posts/media/`** as the single global root for assets.

**URL**: `/posts/media/{filename}`
**Filesystem**: `docs/posts/media/{filename}`

### Configuration
```python
# conventions.py
media_prefix: str = "posts/media"

# paths.py
media_dir = docs_dir / "posts" / "media"
```

### Rationale
1. **Standardization**: Singular "posts" directory for consistent media assets.
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
