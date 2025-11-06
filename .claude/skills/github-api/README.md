# GitHub API Skill

Access plain text versions of GitHub content using URL transformations.

## What This Skill Does

Teaches Claude how to transform GitHub URLs into plain text formats:
- Pull requests → `.diff` or `.patch` files
- Commits → diffs and patches
- Files → raw content
- Comparisons → branch diffs
- Gists → raw content
- Feeds → Atom XML

## When to Use

Use this skill when:
- Users share GitHub URLs (PRs, commits, files)
- Performing code reviews
- Analyzing changes or diffs
- Reading file contents
- Comparing branches
- Monitoring releases or commits

## Quick Examples

```bash
# Pull Request Diff
https://github.com/owner/repo/pull/123
→ https://github.com/owner/repo/pull/123.diff

# Raw File Content
https://github.com/owner/repo/blob/main/README.md
→ https://raw.githubusercontent.com/owner/repo/main/README.md

# Commit Patch
https://github.com/owner/repo/commit/abc123
→ https://github.com/owner/repo/commit/abc123.patch

# Branch Comparison
https://github.com/owner/repo/compare/main...feature
→ https://github.com/owner/repo/compare/main...feature.diff

# Gist Raw
https://gist.github.com/user/123
→ https://gist.github.com/user/123/raw/
```

## Key Features

1. **No HTML Scraping** - Direct access to plain text content
2. **No Authentication** - Works with public repos (raw content has no rate limits)
3. **Multiple Formats** - Choose diff, patch, raw, or feed formats
4. **Whitespace Control** - Add `?w=1` to ignore whitespace changes
5. **Line Numbers** - Use `#L10-L20` for specific line ranges

## URL Patterns

| Content Type | Original Pattern | Plain Text Pattern |
|--------------|------------------|-------------------|
| Pull Request | `/pull/123` | `/pull/123.diff` or `.patch` |
| Commit | `/commit/abc123` | `/commit/abc123.diff` or `.patch` |
| File Blob | `/blob/main/file.py` | `raw.githubusercontent.com/.../main/file.py` |
| Compare | `/compare/a...b` | `/compare/a...b.diff` or `.patch` |
| Gist | `gist.github.com/user/id` | Add `/raw/` suffix |
| Releases | `/releases` | `/releases.atom` |
| Commits | `/commits` | `/commits/branch.atom` |

## Workflow

When a user shares a GitHub URL:
1. **Identify** the URL type
2. **Transform** to plain text format
3. **Fetch** using WebFetch tool
4. **Analyze** the content
5. **Respond** with insights

## Documentation

See `SKILL.md` for complete documentation with:
- Detailed transformation patterns
- Practical examples
- Best practices
- Error handling
- API integration
- Decision trees
