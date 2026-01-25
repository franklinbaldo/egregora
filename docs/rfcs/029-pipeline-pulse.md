# RFC 029: Pipeline Pulse (Rich Telemetry)

**Title:** Pipeline Pulse (Real-Time Telemetry & UX)
**Author:** Visionary
**Status:** Proposed
**Created:** 2026-01-26
**Relation to Moonshot:** This is the first consumer of the [Nervous System](028-the-egregora-nervous-system.md).

## 1. Problem Statement

The current `egregora write` command provides a poor user experience. It often sits silent for minutes while processing large windows, leading users to believe it has hung. There is no visibility into:
- **Cost:** "How much API money am I spending?"
- **Time:** "When will this finish?"
- **Activity:** "What is the AI actually thinking/doing right now?"

## 2. Proposed Solution

Implement **"Pipeline Pulse"**, a rich terminal UI (TUI) using the `rich` library. This UI will subscribe to the events emitted by the Nervous System (RFC 028) to display:

1.  **Global Progress Bar:** Overall windows processed vs total.
2.  **Current Action Spinner:** "Summarizing window 5...", "Generating embeddings...", "creating social card...".
3.  **Live Metrics Panel:**
    - **Cost:** Estimated USD (based on token usage events).
    - **Tokens:** Input/Output counts.
    - **Time:** Elapsed / Remaining.
4.  **The "Pulse" Log:** A scrolling log of "thoughts" or minor events (e.g., "Found 3 images", "Skipping duplicate profile").

### Technical Approach

- **Library:** `rich.progress`, `rich.live`, `rich.layout`.
- **Integration:** Create a `RichConsoleHandler` that subscribes to the Nervous System's event bus.
- **Graceful Fallback:** Detect non-interactive terminals (CI/CD) and fall back to standard logging.

## 3. Value Proposition

- **Trust:** Users know the system is working.
- **Transparency:** Users see the cost accumulation in real-time, preventing "bill shock".
- **Delight:** Turns a boring wait into a "hacker console" experience, aligning with the "Magic" brand pillar.
- **Immediate Utility:** Solves the #1 user friction point (The "Black Box") in < 30 days.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Pipeline Pulse (Real-Time Telemetry)
  As a user running a long blog generation
  I want to see real-time progress and metrics
  So that I know the system is working and how much it costs

  Scenario: Display Phase Progress
    Given the pipeline is in the "PROCESSING" phase
    And there are 10 windows total
    When window 3 is completed
    Then the progress bar should show "30%" completion
    And the current status text should display "Processing Window 4/10..."

  Scenario: Live Cost Estimation
    Given the pipeline is running
    When the "WriterAgent" consumes 1000 input tokens and 200 output tokens
    Then a "TokenUsage" event is emitted
    And the displayed "Estimated Cost" should increase by the appropriate amount
```

## 5. Implementation Plan (30 Days)

- **Week 1:** Define the `Event` schema (RFC 028 prerequisite) and add basic emission points in `write.py`.
- **Week 2:** Implement `RichConsoleHandler` with basic Progress Bar.
- **Week 3:** Add Token/Cost tracking events and the Metrics Panel.
- **Week 4:** Polish, "Pulse" animation, and CI fallback mode.

## 6. Success Metrics

- **User Satisfaction:** Qualitative feedback (via Journal/Discord) on the new UI.
- **Reduced Support:** Fewer "Is it stuck?" questions.
