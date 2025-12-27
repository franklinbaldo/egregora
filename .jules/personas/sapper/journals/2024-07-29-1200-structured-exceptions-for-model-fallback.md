---
title: "💣 Structured Exceptions for Model Fallback"
date: 2024-07-29
author: "Sapper"
emoji: "💣"
type: journal
---

## 💣 2024-07-29 - Summary

**Observation:** The `src/egregora/utils/model_fallback.py` module was violating the "Trigger, Don't Confirm" principle. The `get_openrouter_free_models` function swallowed network errors (`httpx.HTTPError`), returning an empty list and hiding the failure from the caller. Additionally, `create_fallback_model` raised generic `ValueError` and `TypeError` exceptions for configuration problems.

**Action:** I executed a full Test-Driven Development refactoring to make these failure modes explicit and structured.
1.  **Established Hierarchy:** I created a new `ModelError` exception hierarchy in `src/egregora/utils/exceptions.py`, with specific exceptions for `OpenRouterAPIError` and `ModelConfigurationError`.
2.  **TDD (RED):** I created a new test file, `tests/unit/utils/test_model_fallback.py`, and wrote a suite of failing tests asserting that the new, specific exceptions were raised under the correct failure conditions (network errors, invalid model types, missing API keys).
3.  **TDD (GREEN):** I refactored `get_openrouter_free_models` to catch `httpx.HTTPError` and re-raise it as `OpenRouterAPIError`. I then refactored `create_fallback_model` to raise `ModelConfigurationError` for configuration issues.
4.  **TDD (VERIFY):** I ran the test suite and confirmed all tests passed, ensuring the safety and correctness of the new logic.

**Reflection:** This mission successfully hardened the model fallback utility, making its failure modes explicit and informative. This is a critical improvement for the reliability of the entire LLM subsystem. During my initial reconnaissance, I noted that several other files in the `utils` directory are already covered by open PRs. The remaining files (`async_utils.py`, `env.py`, `metrics.py`, `paths.py`, `rate_limit.py`, `retry.py`, and `text.py`) are either too simple or do not contain significant exception handling logic. Therefore, the `utils` directory is likely complete for now. My next mission should focus on another area, perhaps the `llm` package, to continue my work of structuring exceptions.
