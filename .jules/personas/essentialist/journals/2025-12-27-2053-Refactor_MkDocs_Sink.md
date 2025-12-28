---
title: "💎 Refactoring the MkDocs Sink for Declarative Purity"
date: 2025-12-27
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-27 - Refactoring the MkDocs Sink
**Observation:** The `MkDocsOutputSink` in `src/egregora_v3/infra/sinks/mkdocs.py` contained two violations of the Essentialist Heuristics. The `_generate_frontmatter` method used imperative string building to create YAML, violating the "Data over logic" principle. The `_get_filename` method used a verbose chain of `if` statements, violating the "Declarative over imperative" principle.

**Action:** I refactored both methods following a strict TDD process. I added a new test to validate the YAML structure, which initially failed. Then, I changed `_generate_frontmatter` to build a dictionary and serialize it with the `pyyaml` library. I also simplified `_get_filename` to use a declarative `next()` pattern to find the first valid name. All tests passed, confirming the changes were safe.

**Reflection:** This refactoring highlights a common anti-pattern: generating structured data formats (like YAML, JSON, or XML) using manual string manipulation. It's almost always better to build a native data structure and use a trusted serialization library. This separates data from presentation and eliminates an entire class of formatting and escaping bugs. Future work should scan for other sinks or adapters that perform manual string generation and refactor them similarly. The `_write_index` method in the same file is another candidate, as it builds Markdown imperatively.
