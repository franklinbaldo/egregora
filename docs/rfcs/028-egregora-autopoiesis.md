# 🔭 RFC 028: Egregora Autopoiesis

**Feature**: Egregora Autopoiesis (Self-Optimization)
**Authors**: @visionary
**Status**: Proposed
**Created**: 2026-01-28
**Moonshot**: Yes

---

## 1. Problem Statement

Egregora's "intelligence" is currently hardcoded. The system prompts, chunking strategies, and temperature settings are static values defined by developers in `src/egregora/config/` or `src/egregora/templates/`.

However, "one size fits all" fails for diverse teams. A highly technical engineering team needs different summarization prompts than a creative writing group. Currently, improving these requires a human to:
1.  Read the output.
2.  Notice it's suboptimal.
3.  Manually edit the Jinja2 templates or YAML config.
4.  Re-run and hope it's better.

This manual feedback loop is slow, brittle, and rarely happens, leading to "Prompt Rot" where the system's performance degrades relative to user expectations.

## 2. Proposed Solution

We propose **Egregora Autopoiesis** (Self-Creation).

The system will treat its own configuration and prompts as "mutable state" that it can optimize over time based on feedback.

**Core Loop:**
1.  **Execute**: Run the pipeline (Chat -> Blog).
2.  **Observe**: A new `CriticAgent` evaluates the output against the input.
3.  **Reflect**: The agent identifies discrepancies (e.g., "The post missed the sarcasm in the chat").
4.  **Mutate**: The system proposes a "Patch" to its own `system_prompt` or `config.yaml` to fix the issue for next time.
5.  **Apply**: (Optional/Human-in-the-loop) The patch is applied.

## 3. Value Proposition

- **Evergreen Quality**: The system improves with every run, tailoring itself to the specific unique voice of the team.
- **Zero-Config**: Users don't need to learn "Prompt Engineering". The system engineers itself.
- **Resilience**: If a new model version (e.g., Gemini 2.0) behaves differently, Egregora detects the drift and auto-corrects its prompting strategy.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Autopoiesis (Self-Optimization)
  As a user
  I want Egregora to learn from its mistakes
  So that I don't have to manually tune prompts forever

Scenario: Auto-Correction of Tone
  Given the system is configured with a "Professional" tone
  And the chat input is highly informal and sarcastic
  And the generated post is "stiff and awkward"
  When the Autopoiesis Loop runs
  Then the system generates a proposal: "Update tone_prompt: Increase informality weight by 20%"
  And the next run produces a post that captures the sarcasm accurately

Scenario: Hallucination Prevention
  Given the system generated a post with a fact not in the source text
  And the `CriticAgent` detects this hallucination
  When the Autopoiesis Loop runs
  Then the system generates a proposal: "Update system_prompt: Add constraint 'Do not invent details'"
  And logs the incident in the optimization journal

Scenario: Stability Guardrail
  Given the system proposes a radical change (Temperature 0.1 -> 0.9)
  When the Safety Check runs
  Then the proposal is rejected or flagged for human review
  And the system falls back to a conservative increment (0.1 -> 0.2)
```

## 5. Implementation Hints

- **The Critic**: Use a different model/provider for the `CriticAgent` to avoid "blind spots" (e.g., if Writer uses Gemini, Critic uses Claude/GPT-4 via API if available, or a larger Gemini model).
- **The Mutable State**: Refactor `settings.py` to load prompts from a `user_overrides.yaml` that the agent has write access to.
- **The Journal**: Leverage the existing `Journal.md` mechanism to store the "Rationale" for every change.

## 6. Risks

- **Feedback Loops**: The system could optimize for the wrong metric (e.g., maximizing length instead of quality).
- **Instability**: A bad update could break the pipeline permanently. *Mitigation*: Strict versioning of configs and "Safe Mode" rollback.
- **Cost**: Running a Critic and Optimizer doubles the token usage.
