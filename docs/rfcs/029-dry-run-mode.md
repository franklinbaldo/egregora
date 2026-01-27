# RFC 029: Dry Run Mode

**Status:** Proposed
**Date:** 2026-01-26
**Author:** Visionary 🔭
**Relation to Moonshot:** RFC 028 (The Active Maintainer)
**Disruption Level:** Low (Quick Win)

## 1. Problem Statement
Running the Egregora pipeline (`egregora write`) is a "black box" operation.
1.  **Cost**: It incurs LLM costs immediately.
2.  **Opacity**: Users don't know how many windows will be created or if their configuration (regex, dates) matches anything until *after* the run.
3.  **Safety**: Before we allow an "Active Maintainer" (RFC 028) to modify code, we need a mechanism to **simulate** actions without side effects.

## 2. Proposed Solution
Implement a `--dry-run` flag for the `egregora write` command.
This mode will:
*   Parse the input file.
*   Apply all filtering logic (dates, regex).
*   Calculate window boundaries.
*   **Estimate token usage and cost** (based on provider pricing).
*   Print a summary report.
*   **SKIP** all LLM calls and file writing (except logs).

## 3. Value Proposition
*   **Cost Control**: Users can see "This run will cost ~$5.00" and decide if it's worth it.
*   **Fast Feedback**: Debugging regex/date filters takes seconds instead of minutes.
*   **Foundation for Autonomy**: Provides the "Simulation Layer" needed for future autonomous agents to "think before they act".

## 4. BDD Acceptance Criteria

```gherkin
Feature: Pipeline Dry Run
  As a User
  I want to simulate a pipeline run without incurring costs
  So that I can validate my configuration and estimate budget

Scenario: Basic Dry Run
  Given a chat export "chat.zip" with 1000 messages
  When I run "egregora write chat.zip --dry-run"
  Then the system should NOT make any API calls to Google Gemini
  And it should output "Dry Run Mode: Active"
  And it should display "Estimated Windows: 10"
  And it should display "Estimated Tokens: ~150,000"
  And it should display "Estimated Cost: ~$0.05"
  And no HTML files should be generated in the output directory

Scenario: Dry Run with filtering
  Given a chat export with messages from "2023" and "2024"
  When I run "egregora write chat.zip --from-date 2025-01-01 --dry-run"
  Then it should display "Messages matching filter: 0"
  And it should warn "No content to process"

Scenario: Dry Run detects configuration errors
  Given a configuration with an invalid "step_unit"
  When I run "egregora write chat.zip --dry-run"
  Then it should fail immediately with a configuration error
  And it should NOT attempt to parse the full file
```

## 5. Implementation Plan (≤30 Days)

*   **Week 1: Core Logic**
    *   [ ] Refactor `write.py` to accept a `dry_run` boolean.
    *   [ ] Implement `TokenEstimator` service (simple math based on char count / 4).
    *   [ ] Abstract LLM calls behind a facade that returns mocks if `dry_run=True`.

*   **Week 2: Reporting**
    *   [ ] Create `DryRunReporter` class using `rich` library for pretty tables.
    *   [ ] Add cost lookup table for supported models (Gemini Flash/Pro).

*   **Week 3: Integration**
    *   [ ] Hook up CLI flag in `src/egregora/cli/main.py`.
    *   [ ] Add unit tests for `DryRunReporter`.

*   **Week 4: Polish**
    *   [ ] Verify against real large datasets.
    *   [ ] Update documentation.

**Total Effort:** ~10 days of coding.

## 6. Success Metrics
*   **Accuracy**: Token estimation is within ±10% of actual usage.
*   **Speed**: Dry run completes in < 5 seconds for < 10MB inputs.
*   **Adoption**: 50% of manual CLI runs use `--dry-run` first (measured via telemetry if available, or anecdotal).
