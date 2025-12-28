---
title: "💎 Refactor MkDocs Sink to be Declarative"
date: 2025-12-27
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-27 - Summary

**Observation:** The `_write_index` method in `src/egregora_v3/infra/sinks/mkdocs.py` was building a markdown file using imperative Python code (joining a list of strings). This violated the "Declarative over imperative" and "Data over logic" heuristics. The frontmatter generation was also flawed, causing YAML errors.

**Action:** I refactored the method to be declarative and more robust.
1.  **TDD:** I followed a strict Test-Driven Development process. I began by writing a locking test to capture the exact output of the existing method, ensuring the refactoring would be behavior-preserving.
2.  **Refactor:** I replaced the imperative string-building logic with a declarative Jinja2 template (`index.md.jinja`), simplifying the Python code significantly.
3.  **Address Feedback:** I incorporated critical code review feedback by reverting an unrelated change, restoring accidentally deleted tests, and fixing a subtle logic regression related to filename generation for documents without slugs. I added a new test case to cover this regression.
4.  **Fix Bugs:** I identified and corrected a bug in the `_generate_frontmatter` method that was causing `yaml.ComposerError` failures in the tests by removing duplicated `---` delimiters.

**Reflection:** This refactoring is a strong example of the "Declarative over imperative" heuristic. Moving the rendering logic from Python code into a template makes the `MkDocsOutputSink` simpler and more focused on its core responsibility of I/O. The TDD process was invaluable, and the code review step proved critical by catching a significant regression (the deleted tests). This reinforces that a robust pre-commit process is essential for maintaining quality. Future work should continue to identify areas where imperative logic can be replaced with declarative data or templates, especially in other data sinks.