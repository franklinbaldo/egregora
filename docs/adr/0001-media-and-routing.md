# ADR 0001: Media, Profiles, and Routing Conventions

## Context
Egregora V3 architecture requires deterministic and predictable paths for generated content (posts, profiles, media) to support the Atom-centric data model and static site generation (MkDocs). V2 had issues with inconsistent routing and media handling.

## Decision

We adopt the following conventions for V3:

### 1. Unified Post Storage
All generated content (Posts, Profiles, Journal Entries) resides in the `docs/posts/` directory (or configured `posts_dir`). This allows MkDocs to treat them uniformly as blog posts.

### 2. Semantic Identity & Routing
*   **Posts**: Routable via semantic slug + date.
    *   Storage: `docs/posts/{date}-{slug}.md`
    *   URL: `/posts/{date}-{slug}/`
*   **Profiles**: Routable via author UUID (semantic identity for authors).
    *   Storage: `docs/posts/authors/{uuid}.md` (Egregora writes ABOUT the author)
    *   URL: `/posts/authors/{uuid}/`
    *   This keeps profiles as "posts" in the blog structure but grouped.
*   **Announcements**: System events.
    *   Storage: `docs/posts/announcements/{slug}.md`
    *   URL: `/posts/announcements/{slug}/`

### 3. Media Storage
Media files are stored separately from posts to allow for clean separation of assets and content.
*   **Location**: `docs/post/media/`
*   **Subdirectories**:
    *   `docs/post/media/images/`
    *   `docs/post/media/videos/`
    *   `docs/post/media/audio/`
    *   `docs/post/media/files/`
*   **Naming**: Content-addressed UUIDs or Semantic Slugs (preferred for SEO).
    *   Format: `{slug}.{ext}` (e.g., `2025-01-01-sunset.jpg`)

### 4. Ephemeral Staging for Media
To handle large files without memory exhaustion:
*   Media is extracted from ZIPs to a temporary disk directory (`tempfile`).
*   Files > 20MB are uploaded via File API (not inline base64).
*   Files are atomically moved (`shutil.move`) to `docs/post/media/` upon successful processing.

## Consequences
*   **Pros**:
    *   Deterministic URLs.
    *   Clean separation of concerns.
    *   Supports large media files.
    *   Author profiles are treated as first-class content.
*   **Cons**:
    *   Requires strict adherence to directory structure.
    *   Moving files requires filesystem access (handled by Adapter).

## Status
Accepted
