# Task: Implement Feeds Page for Portal Theme

**Status:** TODO
**Priority:** High
**Created:** 2026-01-26
**Tags:** #ux, #frontend, #portal
**Assignee:** forge

## Context
The "Portal" theme includes a link to "RSS Feeds" on the homepage, but the page itself does not exist (404). We need to create a dedicated page that lists the available feeds in a style consistent with the "Portal" aesthetic.

## Specification (BDD)

### Scenario: User navigates to Feeds page
**Given** the generated site is built
**When** a user navigates to `/feeds/`
**Then** they should see a page titled "Data Streams" or "Feeds"
**And** the page should list the available RSS and JSON feeds (e.g., `feed_rss_created.xml`, `feed_json_updated.json`)
**And** the list should be styled using the "Portal" card components (if available) or clean lists
**And** the page should NOT look like a generic Markdown file (use proper frontmatter/macros if needed)

## Implementation Details
- Target file: `src/egregora/rendering/templates/site/docs/feeds/index.md` (Create this file)
- Content:
    - Title: "Data Streams"
    - Description: "Subscribe to the pulse of the collective."
    - Links to:
        - `feed_rss_created.xml` (RSS)
        - `feed_rss_updated.xml` (RSS Updated)
        - `feed_json_created.json` (JSON)
- Ensure the file is included in the `nav` if necessary, or just accessible via the homepage link.

## Verification
- Run `egregora demo`
- Navigate to `http://localhost:8000/feeds/`
- Verify no 404 error and content is visible.
