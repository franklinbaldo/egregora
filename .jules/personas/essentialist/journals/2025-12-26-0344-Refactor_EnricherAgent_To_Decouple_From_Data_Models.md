---
title: "💎 Refactor EnricherAgent To Decouple From Data Models"
date: 2025-12-26
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-26 - Refactor EnricherAgent To Decouple From Data Models

**Observation:** The `EnricherAgent` in `src/egregora_v3/engine/agents/enricher.py` was tightly coupled to the `Entry` data model. It contained business logic for determining if an entry should be enriched, which violated the "Data over logic" and "Small modules over clever modules" heuristics.

**Action:** I refactored the `EnricherAgent` to be a pure, data-in/data-out component.
1.  I removed the internal methods that inspected the `Entry` object (`_has_media_enclosure`, `_should_enrich`).
2.  I changed the public `enrich` method to accept a simple list of media URLs instead of a complex `Entry` object.
3.  I updated the corresponding Jinja2 template to work with the new, simpler data structure.
4.  I followed a strict Test-Driven Development (TDD) process, which was crucial for identifying and correcting a mistake in my initial analysis where I believed the `has_enclosure` property was missing when it was, in fact, present.
5.  I addressed code review feedback by improving the test coverage of the refactored agent.

**Reflection:** This refactoring was a success, but the process highlighted the importance of a thorough "EVALUATE" phase. My initial assumption that the `has_enclosure` property was missing was incorrect and led to some initial confusion. The TDD process, however, ultimately guided me to the correct solution. A significant finding was that the `EnricherAgent` is not yet used anywhere in the application. While this made the refactoring safer, it also suggests that future work should focus on integrating this component into the main pipeline or removing it if it is no longer needed, in accordance with the "Delete over deprecate" heuristic. The code review process also proved valuable, as it prompted me to add a test case for an empty list, making the agent more robust.
