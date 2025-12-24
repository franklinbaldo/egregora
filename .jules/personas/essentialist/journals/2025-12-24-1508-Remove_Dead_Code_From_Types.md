---
title: "💎 Remove Dead Code from Core Types"
date: 2025-12-24
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-24 - Simplify Core Types
**Observation:** The core types module (`src/egregora_v3/core/types.py`) was injecting the `isinstance` function as a global into the Jinja2 template environment. This violates the "Data over logic" heuristic by encouraging imperative checks inside a declarative template. The corresponding Atom feed template (`atom.xml.jinja`) was already using a more appropriate boolean property (`is_document`) to differentiate between entry types, making the `isinstance` global dead code.
**Action:** I removed the unnecessary `isinstance` global. To do this safely, I first followed a Test-Driven Development (TDD) approach by adding a new test to `tests/v3/core/test_feed.py`. This test renders a feed containing both plain `Entry` objects and subclassed `Document` objects, asserting that only the latter received special rendering. After confirming the test passed (locking in the correct behavior), I removed the dead code and re-ran the tests to verify the change was safe.
