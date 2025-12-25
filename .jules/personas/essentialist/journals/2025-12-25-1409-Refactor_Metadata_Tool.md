---
title: "💎 Refactor Metadata Tool for Declarative Purity"
date: "2025-12-25"
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Refactor Metadata Tool
**Observation:** The `get_pipeline_metadata` tool in `src/egregora_v3/engine/tools.py` was imperatively constructing a metadata dictionary. This violated the "Declarative over imperative" heuristic, as the logic for how metadata is composed should belong to the context object itself, not the tool consuming it.
**Action:** I refactored the codebase to align with the heuristic. I introduced a new `full_metadata` property on the `PipelineContext` class to declaratively handle the combination of `run_id` and `metadata`. The `get_pipeline_metadata` tool was then simplified to a single line that returns this property. The entire process was guided by strict Test-Driven Development (TDD), ensuring the change was safe and correct.
**Reflection:** This change exemplifies how moving logic closer to the data it describes simplifies the system. The consumer of the data (`get_pipeline_metadata`) is now decoupled from the implementation details of how that data is constructed. Future work should investigate other tools and agents to see if similar logic can be pushed down into the core data models like `PipelineContext` or `ContentLibrary`, further strengthening the "Data over logic" principle throughout the codebase.
