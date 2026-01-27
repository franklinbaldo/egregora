# 🔭 RFC 029: Reflective Prompt Optimization

**Feature**: Reflective Prompt Optimization
**Authors**: @visionary
**Status**: Proposed
**Created**: 2026-01-28
**Moonshot**: No (Quick Win)
**Relation to Moonshot**: RFC 028 (Egregora Autopoiesis)

---

## 1. Problem Statement

We have no idea if our prompts are good.

We (the developers) write a Jinja template, run it once, say "looks okay", and ship it. Users might be getting suboptimal results (missed nuances, bad formatting) and we never know.

There is no visibility into the *effectiveness* of the prompt *contextualized to the data*.

## 2. Proposed Solution

We will implement the "Observe" and "Reflect" steps of the Autopoiesis loop (RFC 028) as a standalone feature.

**Mechanism:**
1.  **Pipeline Addition**: Add a `ReflectionStep` after the `WriterAgent` finishes.
2.  **Critic Agent**: Instantiate a lightweight `CriticAgent`.
3.  **Analysis**: The Critic reads:
    *   The `System Prompt` used.
    *   The `User Input` (Chat sample).
    *   The `Output` (Blog post).
4.  **Output**: Generates a `reflection.md` report containing:
    *   **Score**: 1-10 on key metrics (Accuracy, Tone, Completeness).
    *   **Critique**: "The prompt failed to emphasize the decision made in line 42."
    *   **Suggestion**: "Consider adding 'Focus on decisions' to the prompt."

**Crucially, this RFC does NOT automatically apply changes.** It just surfaces the insights.

## 3. Value Proposition

- **Immediate Insight**: Developers/Users can see *why* a post failed.
- **Data-Driven Tuning**: We stop guessing what "better prompt" means. The system tells us.
- **Foundation**: It builds the `CriticAgent` infrastructure needed for the full Moonshot.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Reflective Prompt Optimization
  As a developer
  I want to know why a blog post turned out the way it did
  So that I can improve the prompts

Scenario: Successful Reflection
  Given the pipeline has generated a blog post "Sprint 2 Review"
  When the Reflection Step completes
  Then a file "artifacts/reflection.md" is created
  And it contains a "Prompt Critique" section
  And it provides a numerical score for "Context Adherence"

Scenario: Identifying Prompt Weakness
  Given the chat contained a crucial decision about "Database Migration"
  And the generated post omitted it
  When the Reflection Step analyzes the run
  Then the critique explicitly states "The prompt failed to prioritize technical decisions."
  And suggests specific wording to fix it

Scenario: Graceful Degradation
  Given the Critic Agent API fails (e.g., rate limit)
  When the Reflection Step runs
  Then the pipeline should NOT fail
  And a warning is logged
  And the main blog post is still saved successfully
```

## 5. Implementation Plan (30 Days)

- [ ] **Day 1-5**: Design `CriticAgent` using `pydantic-ai`. Define the `Reflection` model (Score, Critique, Suggestion).
- [ ] **Day 6-10**: Integrate `CriticAgent` into the `runner.py` flow (as a post-processing step).
- [ ] **Day 11-20**: Prompt Engineering for the Critic itself (Meta-prompting). Ensure it gives useful, specific advice.
- [ ] **Day 21-25**: Update CLI to output `reflection.md` alongside the post.
- [ ] **Day 26-30**: Unit tests and integration tests.

## 6. Success Metrics

- **Actionable Insights**: % of generated reflections that lead to a manual prompt update by a human (tracked via "Usefulness" feedback or simply adoption).
- **Latency Impact**: Reflection should add < 20% to total execution time.
