# ADR-002: Profile Path Convention

## Status
Accepted

## Context
Profile documents are posts **about** authors written by Egregora. They need to be routed to author-specific directories for organization.

Warning observed: `PROFILE doc missing 'subject' metadata, falling back to posts/`

## Decision
Profile documents go to author subfolders:

**URL**: `/posts/profiles/{author_uuid}/{slug}`
**Filesystem**: `docs/posts/profiles/{author_uuid}/{slug}.md`

### Metadata Requirements
Profile documents MUST have:
```yaml
type: profile
subject: {author_uuid}  # Required for routing
profile_aspect: "interests" | "contributions" | "interactions"
```

### Routing Logic
```python
case DocumentType.PROFILE:
    subject_uuid = document.metadata.get("subject")
    if not subject_uuid:
        logger.warning("PROFILE doc missing 'subject', falling back to posts/")
        return posts_dir / slug
    return posts_dir / "profiles" / subject_uuid / slug
```

## Consequences

### Easier
- Each author has dedicated profile feed
- Easy to find all profiles for a specific author
- Supports incremental profile updates (new posts, not edits)

### Harder
- Profile generator must always set `subject` metadata
- More complex routing logic than flat structure

## Related
- ADR-001: Media Path Convention
- GitHub Issue #1256: Fix Profile Routing
