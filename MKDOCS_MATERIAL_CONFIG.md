# MkDocs Material Configuration Guide

This document explains how to properly configure Material for MkDocs, especially the blog plugin, based on lessons learned during egregora development.

## Critical Rules for Material Blog Plugin

### 1. Directory Structure

Material blog plugin has a **default directory structure** that must be followed:

```
docs/
├── index.md                    # Homepage
├── about.md
├── posts/                      # blog_dir
│   ├── index.md               # Blog entry point (simple or auto-generated)
│   ├── posts/                 # DEFAULT post_dir location
│   │   ├── 2025-01-15-post1.md
│   │   └── 2025-01-16-post2.md
│   └── .authors.yml           # Author metadata (REQUIRED)
└── profiles/
    └── index.md
```

**Key Points:**
- By default, Material expects posts in `blog_dir/posts/` NOT directly in `blog_dir/`
- The `post_dir` config defaults to `"posts"` (relative to `blog_dir`)
- Do NOT use `post_dir: "{blog}"` unless you understand the implications

### 2. Configuration in mkdocs.yml

**CORRECT configuration:**

```yaml
plugins:
  - search:
      lang: en
  - blog:
      blog_dir: posts          # Points to docs/posts/
      blog_toc: true
      post_date_format: long
      post_url_date_format: yyyy/MM/dd
      post_url_format: '{date}/{slug}'
      pagination_per_page: 10
      # post_dir defaults to "posts" - Material will look in docs/posts/posts/

nav:
  - Home: index.md
  - Blog:
    - posts/index.md           # Nested under Blog section
  - Profiles: profiles/index.md
  - About: about.md
```

**WRONG configuration (DO NOT USE):**

```yaml
plugins:
  - blog:
      blog_dir: posts
      post_dir: "{blog}"       # ❌ WRONG: puts posts directly in blog_dir
                               # This breaks blog index and causes conflicts
```

### 3. Blog Index File

The `blog_dir/index.md` file serves as the blog entry point:

**Simple approach (RECOMMENDED):**

```markdown
# Blog
```

Material will auto-inject the blog post list below this heading.

**DO NOT:**
- Create complex index.md files manually
- Try to list posts manually (Material does this automatically)
- Omit the index.md file entirely (required for navigation)

### 4. Post Frontmatter Format

Posts MUST have properly formatted YAML frontmatter:

**CORRECT:**

```yaml
---
title: My Blog Post
date: 2025-01-15              # ✅ Date as YAML date type (unquoted)
slug: my-blog-post
authors:
  - author-id
tags:
  - ai
  - python
summary: Brief description
---

Post content here...
```

**WRONG:**

```yaml
---
date: '2025-01-15'             # ❌ WRONG: quoted string
                               # Material blog plugin requires date objects
---
```

**In Python code:**

```python
import datetime

# Parse date string to date object for proper YAML serialization
front_matter["date"] = datetime.date.fromisoformat(date_string)

# Then use yaml.dump - it will serialize as unquoted date
yaml.dump(front_matter, default_flow_style=False)
```

### 5. Authors Configuration

Material blog plugin REQUIRES an `.authors.yml` file in the `blog_dir`:

```yaml
# docs/posts/.authors.yml
authors:
  author-id:
    name: Author Name
    description: Brief bio
    avatar: https://example.com/avatar.jpg  # REQUIRED field
```

**Key points:**
- File MUST be named `.authors.yml` (with leading dot)
- Located in `blog_dir` (e.g., `docs/posts/.authors.yml`)
- `avatar` field is REQUIRED (use placeholder URL if needed)
- Author IDs in post frontmatter must match IDs in this file

### 6. Navigation Structure

For Material's `navigation.indexes` feature to work properly:

```yaml
theme:
  features:
    - navigation.indexes      # Required for blog index

nav:
  - Home: index.md
  - Blog:
    - posts/index.md         # Nested structure for indexes feature
  - Profiles: profiles/index.md
```

## Common Mistakes to Avoid

### ❌ Mistake 1: Using `post_dir: "{blog}"`

```yaml
plugins:
  - blog:
      blog_dir: posts
      post_dir: "{blog}"      # ❌ DON'T DO THIS
```

**Why wrong:** This puts posts directly in `blog_dir` (e.g., `docs/posts/`) which conflicts with `blog_dir/index.md`. Material can't distinguish between the blog index and actual posts.

**Correct:** Omit `post_dir` (uses default `"posts"`) or set to another subdirectory name.

### ❌ Mistake 2: Quoted dates in frontmatter

```yaml
date: '2025-01-15'           # ❌ String with quotes
```

**Why wrong:** Material blog plugin's date parser expects a YAML date type, not a string.

**Correct:** Use unquoted date `date: 2025-01-15` or serialize from Python `datetime.date` object.

### ❌ Mistake 3: Missing .authors.yml

```
docs/posts/
├── index.md
└── posts/
    └── 2025-01-15-post.md
# ❌ Missing .authors.yml
```

**Why wrong:** Material blog plugin throws error "Couldn't find author 'author-id'" when posts reference authors.

**Correct:** Create `docs/posts/.authors.yml` with all author definitions.

### ❌ Mistake 4: Manually creating blog index content

```markdown
# Blog

Welcome to my blog!

## Recent Posts

- [Post 1](2025-01-15-post1.md)
- [Post 2](2025-01-16-post2.md)
```

**Why wrong:** Material auto-generates the post list. Manual links create duplicate/conflicting content.

**Correct:** Keep index.md minimal - just heading. Material handles the rest.

## Directory Structure Configuration

In egregora, we configure paths to match Material's expectations:

```python
# src/egregora/config/site.py
blog_path = Path(blog_dir)  # e.g., "posts"
if blog_path.is_absolute():
    posts_dir = blog_path / "posts"
else:
    # Material expects posts in blog_dir/posts/ by default
    posts_dir = (docs_dir / blog_path / "posts").resolve()
```

This ensures:
- `blog_dir = "posts"` → `docs/posts/`
- `posts_dir` → `docs/posts/posts/` (where actual .md files go)
- `blog_index` → `docs/posts/index.md` (blog entry point)

## Scaffolding Template

When creating sites, the blog index should be minimal:

```python
# src/egregora/publication/site/scaffolding.py
blog_index_path = posts_dir.parent / "index.md"  # posts_dir is blog_dir/posts/
if not blog_index_path.exists():
    # Simple heading - Material renders post list below
    blog_index_path.write_text("# Blog\n", encoding="utf-8")
```

## Testing Checklist

Before deploying, verify:

1. ✅ Posts are in `docs/blog_dir/posts/` (not `docs/blog_dir/`)
2. ✅ `.authors.yml` exists in `blog_dir` with all author IDs
3. ✅ All `avatar` fields in `.authors.yml` are defined
4. ✅ Post dates are unquoted in frontmatter (`date: 2025-01-15`)
5. ✅ Blog index exists at `docs/blog_dir/index.md`
6. ✅ Navigation uses nested structure (`Blog: - posts/index.md`)
7. ✅ Run `mkdocs build` without errors
8. ✅ Check `/posts/` URL shows post listings

## Documentation References

- [Material Blog Plugin Docs](https://squidfunk.github.io/mkdocs-material/plugins/blog/)
- [Blog Setup Guide](https://squidfunk.github.io/mkdocs-material/setup/setting-up-a-blog/)
- [Post Format](https://squidfunk.github.io/mkdocs-material/plugins/blog/#posts)
- [Authors Config](https://squidfunk.github.io/mkdocs-material/plugins/blog/#config.authors_file)

## Troubleshooting

### "Expected metadata to be defined but found nothing"

**Cause:** Material thinks `blog_dir/index.md` is a post (when using `post_dir: "{blog}"`).

**Fix:** Remove `post_dir: "{blog}"` config and move posts to `blog_dir/posts/`.

### "Error reading metadata 'date': Expected type: <class 'datetime.date'>"

**Cause:** Date field is quoted string `'2025-01-15'` instead of date.

**Fix:** Remove quotes or parse to Python `datetime.date` before YAML serialization.

### "Couldn't find author 'xyz'"

**Cause:** Missing or incorrect `.authors.yml` file.

**Fix:** Create `blog_dir/.authors.yml` with author definitions including `avatar` field.

### Posts not appearing at /posts/ URL

**Causes:**
1. Posts in wrong directory (`blog_dir/` instead of `blog_dir/posts/`)
2. Missing `blog_dir/index.md` file
3. Incorrect navigation structure in `mkdocs.yml`

**Fix:** Follow the directory structure and navigation patterns shown above.

## Summary

**Golden Rules:**
1. Use Material's default `blog_dir/posts/` structure
2. Keep dates unquoted in YAML frontmatter
3. Always include `.authors.yml` with `avatar` fields
4. Keep blog index minimal (just `# Blog`)
5. Always consult official Material docs before customizing
