## 2024-05-23 - [Unicode Normalization Redundancy]
**Learning:** `unicodedata.normalize("NFKC", ...)` automatically handles compatibility characters like `\u202f` (Narrow No-Break Space), converting them to standard spaces. Explicit `replace` calls after NFKC normalization are often redundant and wasteful (O(N) scans).
**Action:** Before implementing manual string replacements for unicode characters, check if they are covered by standard normalization forms.
