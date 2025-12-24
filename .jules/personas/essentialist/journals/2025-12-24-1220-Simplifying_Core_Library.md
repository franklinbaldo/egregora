---
title: "💎 Simplifying the Core Library"
date: 2025-12-24
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-24 - Refactoring the Core Library
**Observation:** The 'core' library in 'src/egregora_v3/core' contained several violations of the Essentialist Heuristics. The configuration system was over-engineered with implicit logic, and the `Document.create` method had too many flexible paths for identity. Additionally, the `Feed.to_xml` method used imperative logic (`isinstance`) within a declarative template.
**Action:** I refactored the 'core' library to address these issues. I removed the custom settings loader from `config.py` in favor of standard, explicit `pydantic-settings` behavior. I simplified the `Document.create` factory by removing the `id_override` parameter, enforcing a single path for identity based on the slug. Finally, I replaced the `isinstance` check in the Atom XML template with an explicit `is_document` property on the `Entry` and `Document` models, adhering to the "Data over logic" principle. All changes were made following a strict TDD process.
