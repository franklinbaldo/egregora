## 2024-05-23 - [Unicode Normalization Redundancy]
**Learning:** `unicodedata.normalize("NFKC", ...)` automatically handles compatibility characters like `\u202f` (Narrow No-Break Space), converting them to standard spaces. Explicit `replace` calls after NFKC normalization are often redundant and wasteful (O(N) scans).
**Action:** Before implementing manual string replacements for unicode characters, check if they are covered by standard normalization forms.

## 2025-05-15 - [Unicode Normalization Performance]
**Learning:** `unicodedata.normalize` is expensive (O(N)). For mostly ASCII text (like English chat logs), `str.isascii()` check (O(N) highly optimized C) is much faster.
**Action:** Add an ASCII fast-path to text normalization routines: `if value.isascii(): return simple_escape(value)`.

## 2025-05-15 - [Hashing Overhead in Loops]
**Learning:** Repeatedly hashing the same string (e.g., `uuid.uuid5` for the same author in a chat log) is a significant CPU sink. SHA-1 is fast, but 100k times is slow.
**Action:** Use a local dictionary cache for hashing recurring identifiers in loops.

## 2025-05-15 - [Ibis Lazy Execution]
**Learning:** Calling `.count().execute()` on an Ibis table just to check for emptiness breaks lazy evaluation and forces an immediate materialization/scan.
**Action:** Trust the data flow or use lazy checks. Avoid `.execute()` inside transformation functions unless absolutely necessary for control flow that depends on data values.
