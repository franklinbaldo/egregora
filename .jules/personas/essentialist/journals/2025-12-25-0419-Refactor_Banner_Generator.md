---
title: "💎 Refactor Banner Generator for Declarative Configuration"
date: 2025-12-25
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Refactor Banner Generator
**Observation:** The `GeminiV3BannerGenerator` in `src/egregora_v3/engine/banner/generator.py` used an imperative approach to build the `config_params` dictionary for the image generation request. This violated the "Declarative over imperative" and "Data over logic" heuristics by using conditional logic to construct a data structure.
**Action:** I refactored the `generate` method to be more declarative. Following a strict Test-Driven Development (TDD) process, I first created a new test suite to lock in the existing behavior, as none existed. Then, I replaced the imperative dictionary construction with a single conditional expression that directly creates the `GenerateImagesConfig` object if an `aspect_ratio` is present. All tests passed, confirming the change was safe and effective.
**Reflection:** The lack of existing tests for this module highlights a potential gap in the project's test coverage. Future work should focus on ensuring that all new code is accompanied by tests and that existing, untested code is progressively covered. This will make future refactoring efforts safer and more efficient.
