# ADR-002: Author Feed Path Convention (Profiles + Announcements)

## Status
Accepted

## Context
Authors need a unified feed showing both:
1. **PROFILE documents**: Egregora's analyses about the author
2. **ANNOUNCEMENT documents**: User command events (bio updates, alias changes, etc.)

Warning observed: `PROFILE doc missing 'subject' metadata, falling back to posts/`

This ADR establishes the **feed-style layout** where each author has their own directory containing all documents about them or by them.

## Decision
Documents with `subject` metadata route to author-specific subdirectories:

**URL**: `/posts/profiles/{author_uuid}/{slug}`
**Filesystem**: `docs/posts/profiles/{author_uuid}/{slug}.md`

### Document Types in Author Feed

#### 1. PROFILE Documents
- **Purpose**: Egregora's analytical posts ABOUT the author
- **Examples**: "Alice: Photography Techniques", "Bob: Technical Contributions"
- **Slug format**: `{date}-{aspect}-{author_id}` (e.g., `2025-03-15-photography-550e8400`)
- **Append-only**: Each analysis creates a NEW post (never overwrites)

#### 2. ANNOUNCEMENT Documents
- **Purpose**: User command events (bio changes, alias updates, avatar changes)
- **Examples**: "Alice Updated Bio", "Bob Set New Alias"
- **Slug format**: `{date}-{event_type}-{author_id}` (e.g., `2025-03-15-bio_update-550e8400`)
- **Append-only**: Each command creates a NEW post

### Metadata Requirements

**PROFILE documents MUST have:**
```yaml
type: profile
subject: {author_uuid}     # Required for routing
slug: {meaningful-slug}    # Semantic identifier
authors: [egregora]        # Egregora is the author OF the post
date: {YYYY-MM-DD}         # For temporal ordering
```

**ANNOUNCEMENT documents MUST have:**
```yaml
type: announcement
subject: {author_uuid}     # Required for routing
slug: {date}-{event_type}-{author_id}
event_type: bio_update | alias_set | avatar_update
actor: {author_uuid}       # Who performed the action
date: {YYYY-MM-DD}
```

### Routing Logic

```python
case DocumentType.PROFILE | DocumentType.ANNOUNCEMENT:
    subject_uuid = document.metadata.get("subject")
    if not subject_uuid:
        logger.warning("%s doc missing 'subject', falling back", document.type)
        return fallback_dir / slug
    return posts_dir / "profiles" / subject_uuid / slug
```

### Feed-Style Benefits

1. **Complete author timeline**: All content about/by an author in one place
2. **Chronological ordering**: Date-prefixed slugs enable temporal sorting
3. **Append-only architecture**: History is preserved, never overwritten
4. **Context for LLM**: Profile history feeds into future analyses via Jinja templates
5. **MkDocs blog integration**: Each author directory works as a blog category

## Consequences

### Easier
- Unified feed per author showing evolution over time
- Easy to find all content related to a specific author
- Profile history available for LLM context (avoids repetition)
- Natural blog-style layout in MkDocs
- Clear separation between content types via naming

### Harder
- Generators MUST always set `subject` metadata (validated at creation time)
- More complex routing logic than flat structure
- Profile history loading adds context fetch step

### Implementation Requirements
- `validate_profile_document()` enforces `subject` metadata
- `_generate_meaningful_slug()` creates semantic, unique slugs
- `get_profile_history_for_context()` compiles timeline for LLM
- URL conventions route both PROFILE and ANNOUNCEMENT to author feeds

## Related
- ADR-001: Media Path Convention
- GitHub Issue #1256: Fix Profile Routing to Author Subdirectories
- `src/egregora/agents/profile/generator.py`: Append-only profile generation
- `src/egregora/agents/profile/history.py`: Jinja-based history compilation
- `src/egregora/agents/commands.py`: ANNOUNCEMENT document creation
