---
name: github-api
description: Access plain text versions of GitHub content (diffs, patches, raw files) using GitHub's URL transformations. Use when users share GitHub URLs for PRs, commits, files, or gists and you need to analyze the actual content. Works for pull requests, commits, file blobs, comparisons, and gists.
---

# GitHub Plain Text API Access

This skill enables direct access to plain text versions of GitHub content without HTML rendering, perfect for analyzing code changes, reviewing files, and processing GitHub data.

## Overview

GitHub provides multiple URL "hacks" that return content in plain text or structured formats:
- **PRs & Commits** → `.diff` or `.patch` files
- **File content** → Raw text via `raw.githubusercontent.com`
- **Gists** → Raw files
- **Markdown** → Unrendered via `?plain=1`
- **Feeds** → Atom XML for releases and commits

## Quick Start

### Pull Request Diffs

**Standard PR URL:**
```
https://github.com/owner/repo/pull/123
```

**Plain text diff:**
```
https://github.com/owner/repo/pull/123.diff
```

**Patch format (with metadata):**
```
https://github.com/owner/repo/pull/123.patch
```

**Ignore whitespace:**
```
https://github.com/owner/repo/pull/123.diff?w=1
```

## URL Transformations

### 1. Pull Requests → Diff/Patch

Transform any PR URL by appending `.diff` or `.patch`:

**Examples:**
```
# Original
https://github.com/franklinbaldo/egregora/pull/600

# Unified diff
https://github.com/franklinbaldo/egregora/pull/600.diff

# Mail-ready patch (includes commit messages, author info)
https://github.com/franklinbaldo/egregora/pull/600.patch

# Ignore whitespace changes
https://github.com/franklinbaldo/egregora/pull/600.diff?w=1
```

**When to use:**
- Code reviews: Analyze exact changes
- CI/CD: Process diffs programmatically
- Linters: Check only modified lines
- Documentation: Show what changed

### 2. Commits → Diff/Patch

Works identically to PRs:

**Examples:**
```
# Original
https://github.com/franklinbaldo/egregora/commit/dee113a

# Diff format
https://github.com/franklinbaldo/egregora/commit/dee113a.diff

# Patch format
https://github.com/franklinbaldo/egregora/commit/dee113a.patch
```

**When to use:**
- Review single commits
- Extract commit metadata
- Apply patches locally
- Analyze specific changes

### 3. Compare Views → Diff/Patch

Compare two branches, tags, or commits:

**Examples:**
```
# Original compare
https://github.com/franklinbaldo/egregora/compare/main...feature-branch

# Diff format
https://github.com/franklinbaldo/egregora/compare/main...feature-branch.diff

# Patch format
https://github.com/franklinbaldo/egregora/compare/main...feature-branch.patch

# Ignore whitespace
https://github.com/franklinbaldo/egregora/compare/main...feature-branch.diff?w=1
```

**When to use:**
- Review entire feature branches
- Generate release notes
- Audit changes between versions
- Pre-merge analysis

### 4. File Content → Raw Text

Convert any blob URL to raw content:

**Method 1: raw.githubusercontent.com**
```
# Original
https://github.com/franklinbaldo/egregora/blob/main/README.md

# Raw content
https://raw.githubusercontent.com/franklinbaldo/egregora/main/README.md
```

**Method 2: ?raw=1 parameter**
```
# Redirects to raw.githubusercontent.com
https://github.com/franklinbaldo/egregora/blob/main/README.md?raw=1
```

**Pattern:**
```
# Original blob URL
https://github.com/<owner>/<repo>/blob/<ref>/<path/to/file>

# Raw content
https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path/to/file>
```

**When to use:**
- Read file contents directly
- Download configuration files
- Process text files
- Fetch scripts for execution

### 5. Gist Raw Content

**Latest version of a gist file:**
```
https://gist.github.com/<user>/<gist-id>/raw/
```

**Specific file in gist:**
```
https://gist.githubusercontent.com/<user>/<gist-id>/raw/<filename>
```

**Example:**
```
# Gist URL
https://gist.github.com/franklinbaldo/abc123

# Raw content (latest)
https://gist.github.com/franklinbaldo/abc123/raw/

# Specific file
https://gist.githubusercontent.com/franklinbaldo/abc123/raw/example.py
```

**When to use:**
- Fetch shared code snippets
- Download configuration examples
- Process gist data programmatically

### 6. Unrendered Markdown

View Markdown source without rendering:

**Examples:**
```
# Original
https://github.com/franklinbaldo/egregora/blob/main/README.md

# Plain text (still HTML page, but content in <pre>)
https://github.com/franklinbaldo/egregora/blob/main/README.md?plain=1

# With line numbers
https://github.com/franklinbaldo/egregora/blob/main/README.md?plain=1#L14-L30
```

**When to use:**
- Analyze Markdown formatting
- Copy exact source text
- Check for rendering issues
- Link to specific lines

### 7. Atom Feeds (XML)

**Releases feed:**
```
https://github.com/franklinbaldo/egregora/releases.atom
```

**Commits feed (per branch):**
```
https://github.com/franklinbaldo/egregora/commits/main.atom
https://github.com/franklinbaldo/egregora/commits/feature-branch.atom
```

**When to use:**
- Monitor releases programmatically
- Build RSS readers
- Track commit activity
- Integration with feed aggregators

## Advanced: GitHub API with Media Types

For scripting and API access, use `Accept` headers to get diff/patch content:

**Examples:**
```bash
# Get PR diff via API
curl -H "Accept: application/vnd.github.diff" \
  https://api.github.com/repos/franklinbaldo/egregora/pulls/600

# Get PR patch via API
curl -H "Accept: application/vnd.github.patch" \
  https://api.github.com/repos/franklinbaldo/egregora/pulls/600

# Get commit diff via API
curl -H "Accept: application/vnd.github.diff" \
  https://api.github.com/repos/franklinbaldo/egregora/commits/dee113a
```

**Media types:**
- `application/vnd.github.diff` - Unified diff format
- `application/vnd.github.patch` - Patch format with metadata
- `application/vnd.github.raw` - Raw file content
- `application/vnd.github.html` - Rendered HTML

## Practical Workflow Examples

### Example 1: Code Review Assistant

When a user shares a PR for review:

```markdown
User: "Can you review this PR? https://github.com/franklinbaldo/egregora/pull/600"

Claude workflow:
1. Transform URL: https://github.com/franklinbaldo/egregora/pull/600.diff
2. Fetch the diff using WebFetch
3. Analyze changes in plain text
4. Provide code review feedback
```

### Example 2: File Content Analysis

When analyzing a specific file:

```markdown
User: "What does this file do? https://github.com/franklinbaldo/egregora/blob/main/src/egregora/privacy/anonymizer.py"

Claude workflow:
1. Transform to raw: https://raw.githubusercontent.com/franklinbaldo/egregora/main/src/egregora/privacy/anonymizer.py
2. Fetch raw content
3. Analyze code structure
4. Explain functionality
```

### Example 3: Compare Branches

When checking differences between branches:

```markdown
User: "What changed between main and this feature branch?"

Claude workflow:
1. Create compare URL: https://github.com/franklinbaldo/egregora/compare/main...feature-branch.diff
2. Fetch diff
3. Summarize changes by file
4. Highlight key modifications
```

### Example 4: Commit Investigation

When investigating a specific commit:

```markdown
User: "What did commit dee113a change?"

Claude workflow:
1. Transform: https://github.com/franklinbaldo/egregora/commit/dee113a.patch
2. Fetch patch (includes commit message + author)
3. Parse changes
4. Explain purpose and impact
```

## URL Pattern Recognition

### Recognize these patterns in user messages:

**Pull Request:**
```
github.com/{owner}/{repo}/pull/{number}
→ Add .diff or .patch
```

**Commit:**
```
github.com/{owner}/{repo}/commit/{sha}
→ Add .diff or .patch
```

**File Blob:**
```
github.com/{owner}/{repo}/blob/{ref}/{path}
→ Replace github.com with raw.githubusercontent.com
→ Remove /blob/
```

**Compare:**
```
github.com/{owner}/{repo}/compare/{base}...{head}
→ Add .diff or .patch
```

**Gist:**
```
gist.github.com/{user}/{id}
→ Add /raw/ for latest
→ Use gist.githubusercontent.com/{user}/{id}/raw/{file}
```

## Decision Tree: Which Format to Use?

### Use `.diff` when:
- You need a unified diff format
- Analyzing line-by-line changes
- Processing with diff tools
- Comparing code changes
- Lightweight format preferred

### Use `.patch` when:
- You need commit metadata (author, message, date)
- Applying changes with `git apply`
- Generating changelogs
- Email-based workflows
- Full context is important

### Use `raw` when:
- Reading complete file contents
- Downloading files
- Processing configuration
- Executing scripts
- No diff needed, just content

### Use `?plain=1` when:
- Analyzing Markdown formatting
- Showing source in documentation
- Linking to specific lines
- Debugging rendering issues

### Use `.atom` when:
- Monitoring for updates
- RSS/feed integration
- Tracking releases or commits
- Building notification systems

## Best Practices

### 1. Always Transform User URLs

When a user shares a GitHub URL, automatically:
1. Identify the URL type (PR, commit, file, etc.)
2. Determine the best plain text format
3. Transform the URL
4. Fetch the content
5. Analyze and respond

**Example:**
```markdown
User: "Check this PR: https://github.com/owner/repo/pull/42"

Don't just visit the URL. Instead:
1. Transform: https://github.com/owner/repo/pull/42.diff
2. Fetch diff
3. Analyze changes
4. Provide insights
```

### 2. Use Whitespace Filtering

For cleaner diffs, add `?w=1` to ignore whitespace:
```
# Before
https://github.com/owner/repo/pull/42.diff

# After (ignore whitespace)
https://github.com/owner/repo/pull/42.diff?w=1
```

### 3. Prefer Raw Content for Files

Don't parse HTML when you can get raw text:
```
# Bad: Scraping rendered HTML
https://github.com/owner/repo/blob/main/README.md

# Good: Direct raw content
https://raw.githubusercontent.com/owner/repo/main/README.md
```

### 4. Check for Private Repos

Raw URLs respect GitHub permissions:
- Public repos: Anyone can access raw content
- Private repos: Requires authentication
- If fetch fails, inform user about access requirements

### 5. Handle Large Diffs Gracefully

Large PRs/commits may have truncated diffs:
- GitHub truncates very large diffs
- Check for "diff is too large" messages
- Consider fetching specific files instead
- Use API with pagination for complete data

## Error Handling

### Common Issues

**404 Not Found:**
- Check repo/branch/file exists
- Verify user has access (private repos)
- Confirm SHA/ref is correct

**Redirect Required:**
- `github.com` URLs may redirect
- Follow redirects automatically
- Use `raw.githubusercontent.com` directly for files

**Rate Limiting:**
- Anonymous API calls: 60/hour
- Authenticated: 5,000/hour
- Raw content URLs: No rate limit
- Use raw URLs when possible

**Large Content:**
- Files over 1MB may not display
- Use API with authentication for large files
- Consider streaming for very large files

## Integration with Claude Code Tools

### Use WebFetch for Content

```markdown
Claude workflow:
1. User shares: https://github.com/owner/repo/pull/123
2. Transform: https://github.com/owner/repo/pull/123.diff
3. WebFetch with prompt: "Extract the code changes"
4. Analyze fetched diff
5. Respond with insights
```

### Combine with Other Skills

**With code review:**
- Fetch `.diff` → analyze changes → provide feedback

**With documentation:**
- Fetch raw markdown → check formatting → suggest improvements

**With testing:**
- Fetch `.patch` → identify test coverage gaps → recommend tests

## Quick Reference

```bash
# Pull Request / Commit
{url}.diff                   # Unified diff
{url}.patch                  # Patch with metadata
{url}.diff?w=1              # Ignore whitespace

# File Content
# Replace: github.com/{owner}/{repo}/blob/{ref}/{path}
# With:     raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}

# Or append
{blob_url}?raw=1            # Redirects to raw

# Gist
gist.github.com/{user}/{id}/raw/                    # Latest
gist.githubusercontent.com/{user}/{id}/raw/{file}   # Specific

# Markdown
{blob_url}?plain=1          # Unrendered source
{blob_url}?plain=1#L10-L20  # With line numbers

# Feeds
{repo_url}/releases.atom           # Releases
{repo_url}/commits/{branch}.atom   # Commits

# Compare
{repo_url}/compare/{base}...{head}.diff    # Diff
{repo_url}/compare/{base}...{head}.patch   # Patch
```

## Summary

When users share GitHub URLs:
1. **Recognize** the URL type (PR, commit, file, compare, gist)
2. **Transform** to appropriate plain text format
3. **Fetch** the content using WebFetch
4. **Analyze** the plain text content
5. **Respond** with insights

This skill eliminates the need to scrape HTML and provides direct access to GitHub's structured content formats.

Remember: GitHub makes it easy to access plain text versions of almost any content—you just need to know the right URL patterns!
