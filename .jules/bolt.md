## 2024-05-23 - [Unicode Normalization Redundancy]
**Learning:** `unicodedata.normalize("NFKC", ...)` automatically handles compatibility characters like `\u202f` (Narrow No-Break Space), converting them to standard spaces. Explicit `replace` calls after NFKC normalization are often redundant and wasteful (O(N) scans).
**Action:** Before implementing manual string replacements for unicode characters, check if they are covered by standard normalization forms.

## 2025-05-21 - [Efficient Frontmatter Parsing]
**Learning:** Reading entire files just to extract YAML frontmatter is a major performance bottleneck for large markdown files. Streaming the file and stopping after the second `---` delimiter avoids loading the full content into memory.
**Action:** Use `read_frontmatter_only` instead of `path.read_text()` when only metadata is needed from markdown files.
