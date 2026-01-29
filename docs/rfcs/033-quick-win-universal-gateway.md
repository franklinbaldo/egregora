# 🔭 RFC 033: Universal LLM Gateway

**Status**: Proposed
**Type**: Quick Win ⚡
**Driver**: Visionary
**Date**: 2026-01-26

---

## 1. Relation to Moonshot (RFC 032)

The **Moonshot (Egregora Live)** envisions a local, interactive intelligence server. For that vision to be truly "Private" and "Resilient", it cannot depend solely on Google's cloud.

This **Quick Win** builds the foundation by abstracting the LLM layer, allowing Egregora to plug into *any* intelligence source—including local models (Ollama) which are critical for a free, private "Echo" interface.

---

## 2. Problem Statement

**The Assumption**: "Users will use Google Gemini because it's free/cheap."

**The Friction**:
-   **Vendor Lock-in**: The codebase hardcodes `google-gla` in defaults and retry logic.
-   **Privacy Concerns**: Many users refuse to send personal chat logs to Google.
-   **Resilience**: If Google API goes down or changes pricing, Egregora breaks.
-   **Quality Ceiling**: Some tasks (creative writing) are better handled by Claude 3.5 Sonnet or GPT-4o.

**The Opportunity**: Pydantic-AI already supports multiple providers. We just need to expose this capability via configuration and a unified factory.

---

## 3. Proposed Solution

**Goal**: Implement a **Configuration-Driven Model Gateway** that supports Google, OpenAI, Anthropic, and OpenAI-compatible endpoints (Ollama/vLLM).

**Changes**:
1.  **Unified Configuration**: Replace hardcoded `DEFAULT_MODEL` with a structured `[models]` config section.
2.  **Factory Pattern**: A centralized `ModelFactory` that instantiates the correct Pydantic-AI model based on the config string (e.g., `openai:gpt-4o`, `ollama:llama3`).
3.  **Fallback Logic**: Allow defining a list of providers. If Primary fails, try Secondary.

**Config Example**:
```toml
[models]
primary = "anthropic:claude-3-5-sonnet"
fallback = ["google-gla:gemini-2.5-flash"]
local = "ollama:mistral"
```

---

## 4. Value Proposition

| Metric | Improvement |
| :--- | :--- |
| **Privacy** | Enables 100% offline processing via Ollama/Llama 3. |
| **Resilience** | 99.9% uptime by falling back between providers. |
| **Quality** | Users can pay for premium models (Claude/GPT-4) for better writing. |

---

## 5. BDD Acceptance Criteria

### Feature: Multi-Provider Support
```gherkin
Feature: Multi-Provider Support
  As a privacy-conscious user
  I want to configure which AI model processes my data
  So that I can control where my data goes

  Scenario: Switching to OpenAI
    Given I have set `EGREGORA_MODEL=openai:gpt-4o`
    And I have a valid `OPENAI_API_KEY`
    When I run the pipeline
    Then the Writer Agent should use GPT-4o for generation
    And the cost should be tracked accordingly

  Scenario: Using Local Ollama
    Given I have set `EGREGORA_MODEL=ollama:llama3`
    When I run the pipeline
    Then no data should be sent to external APIs
    And the system should work offline
```

### Feature: Graceful Provider Fallback
```gherkin
Feature: Graceful Provider Fallback
  As a user with a strict deadline
  I want the system to switch models if one fails
  So that the pipeline finishes without manual intervention

  Scenario: Primary Provider Outage
    Given I have configured Primary: "google" and Fallback: "openai"
    When the Google API returns a 503 Service Unavailable
    Then the system should automatically retry using OpenAI
    And a warning should be logged
    But the pipeline should not crash
```

---

## 6. Implementation Plan (14 Days)

-   [ ] **Day 1-3**: Refactor `settings.py` to support structured model config.
-   [ ] **Day 4-6**: Create `ModelFactory` and abstract `WriterAgent` dependency.
-   [ ] **Day 7-9**: Implement `Ollama` support (OpenAI-compatible endpoint).
-   [ ] **Day 10-12**: Add Fallback/Retry logic in the Gateway.
-   [ ] **Day 13-14**: Documentation and Examples.

**Success Metrics**:
-   Pipeline runs successfully with `openai:gpt-4o`.
-   Pipeline runs successfully with `ollama:llama3` (offline).
-   Unit tests pass for fallback scenarios.
