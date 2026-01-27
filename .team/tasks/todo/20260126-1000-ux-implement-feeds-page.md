# UX Task: Implement Feeds Page to Fix 404

**Status**: TODO
**Created**: 2026-01-26
**Priority**: High (Fixes Broken Link on Homepage)
**Assignee**: Forge

## Context
The homepage contains a "Quick Navigation" card for "RSS Feeds" that links to `feeds/`. Currently, this page does not exist, resulting in a 404 error. The `mkdocs-rss-plugin` generates XML/JSON feed files, but provides no user-facing index page.

## Requirements
Create a dedicated "Feeds" page that matches the "Portal" design aesthetic (glassmorphism cards) and provides links to all available feeds.

### 1. Create Template File
Create a new file: `src/egregora/rendering/templates/site/docs/feeds/index.md.jinja`

**Content:**
```markdown
---
title: RSS Feeds
hide:
  - toc
---

# Subscribe to Updates

Stay connected with the collective consciousness through our open feeds.

<div class="grid cards" markdown>

-   **RSS Feed (Recent)**

    ![RSS](https://upload.wikimedia.org/wikipedia/commons/4/46/Generic_Feed-icon.svg){ width="24" }

    Standard RSS 2.0 feed of the latest posts. Best for feed readers.

    [:material-rss: Subscribe](../feed_rss_created.xml){ .md-button .md-button--primary }

-   **RSS Feed (Updated)**

    ![RSS](https://upload.wikimedia.org/wikipedia/commons/4/46/Generic_Feed-icon.svg){ width="24" }

    RSS 2.0 feed sorted by most recently updated content.

    [:material-rss: Subscribe](../feed_rss_updated.xml){ .md-button }

-   **JSON Feed (Recent)**

    ![JSON](https://upload.wikimedia.org/wikipedia/commons/c/c9/JSON_vector_logo.svg){ width="24" }

    JSON Feed version 1.1. Good for programmatic consumption.

    [:material-code-json: Subscribe](../feed_json_created.json){ .md-button }

-   **JSON Feed (Updated)**

    ![JSON](https://upload.wikimedia.org/wikipedia/commons/c/c9/JSON_vector_logo.svg){ width="24" }

    JSON Feed version 1.1 sorted by update time.

    [:material-code-json: Subscribe](../feed_json_updated.json){ .md-button }

</div>
```

### 2. Update Scaffolding
Update `src/egregora/output_sinks/mkdocs/scaffolding.py` to:
1.  Register the new template in `templates_to_render`.
2.  Ensure the `docs/feeds` directory is created.

**Snippet for `templates_to_render`:**
```python
(docs_dir / "feeds" / "index.md", "docs/feeds/index.md.jinja"),
```

**Snippet for directory creation (inside `_create_template_files` or similar):**
```python
(docs_dir / "feeds").mkdir(parents=True, exist_ok=True)
```
*(Note: `mkdir` might happen automatically if the scaffolding logic handles parent directories for templates, which it seems to do: `target_path.parent.mkdir(parents=True, exist_ok=True)` in `_create_template_files`. Please verify.)*

## Verification
1.  Run `egregora demo`.
2.  Verify `docs/feeds/index.md` is created.
3.  Serve the site and click "RSS Feeds" on the homepage. It should load the new page.
4.  Click "Subscribe" buttons on the new page. They should open the XML/JSON files.
