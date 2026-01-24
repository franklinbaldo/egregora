# 🔭 RFC 026: The Autonomous Director

**Status:** Draft
**Created:** 2026-01-26
**Persona:** Visionary
**Type:** Moonshot

## Problem Statement
Currently, Egregora is a "dumb" tool. It takes a configuration and executes it blindly. If the output is boring, repetitive, or hallucinatory, the burden is entirely on the user to debug the prompt, adjust the temperature, or tweak the window size. This "Configuration Wall" prevents non-technical users from getting the best out of modern LLMs.

**Assumption to Challenge:** "The user knows the optimal parameters for the AI."
**Reality:** The user knows *what they like*, but they don't know *how to get it*.

## Proposed Solution
**The Autonomous Director** is a meta-agent that sits above the standard pipeline. Instead of a static execution, it treats every generation as an experiment.

1.  **Variation Generation:** For a given set of source messages, the Director may spawn multiple `Writer` agents with slightly different strategies (e.g., "Focus on humor", "Focus on sentiment", "Use short sentences").
2.  **Critic Evaluation:** It uses a "Critic" model (or user feedback history) to score the outputs against a "Quality Rubric".
3.  **Parameter Evolution:** Over time, it uses a genetic algorithm or Bayesian optimization to refine the global system prompts and parameters (`temperature`, `top_p`) to maximize the Quality Score.

It turns Egregora from a **Static Site Generator** into a **Self-Optimizing Narrative Engine**.

## Value Proposition
- **Zero-Config Excellence:** The system gets better the more you use it, without you touching a config file.
- **Personalized Voice:** It learns your specific group's style. If your group is sarcastic, the AI learns to be sarcastic.
- **Resilience:** If a new model version (e.g., Gemini 2.0) changes behavior, the Director automatically adjusts its prompts to compensate.

## BDD Acceptance Criteria

```gherkin
Feature: Autonomous Optimization

  As a user who doesn't know prompt engineering
  I want Egregora to figure out the best settings for my chat
  So that I get engaging stories without technical friction

  Scenario: Implicit Preference Learning
    Given the Director has observed I often "Skip" long posts
    And I often "Share" short, funny posts
    When the next batch of posts is generated
    Then the Director should prioritize "Brevity" and "Humor" strategies
    And the average post length should decrease

  Scenario: Model Adaptation
    Given the underlying model is swapped from "Gemini Flash" to "GPT-4o"
    And the initial outputs are scored low by the internal Critic (e.g., "Too formal")
    When the Director runs its nightly optimization cycle
    Then it should mutate the system prompt to inject "Casualness"
    And the Quality Score should recover
```

## Implementation Hints
- **The Critic:** A separate, smaller LLM chain that evaluates text on specific axes (Coherence, Engagement, Hallucination).
- **The Store:** A database of `(Input, Parameters, Output, Score)` tuples.
- **The Optimizer:** A background worker that analyzes The Store to suggest parameter updates.

## Risks
- **Cost:** Running multiple variations and critics increases token usage significantly (3x-5x).
- **Drift:** The optimizer might over-fit to a specific niche style and lose versatility.
- **Complexity:** Debugging a system that rewrites its own instructions is notoriously difficult.
