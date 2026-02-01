# 🔭 RFC 041: Connection Health Report (The Ghost Report)

**Status**: Proposed
**Type**: Quick Win ⚡
**Driver**: Visionary
**Date**: 2026-02-02

---

## 1. Relation to Moonshot (RFC 040)

The **Moonshot (Egregora Keeper)** envisions an active agent that prompts you to reconnect. This **Quick Win** builds the foundational *metrics* for that vision. Before we can "Nudge", we must first "Measure".

This RFC proposes a simple analytical report that visualizes the state of your relationships.

---

## 2. Problem Statement

**The Assumption**: "Users know who they are losing touch with."

**The Friction**:
-   **Invisible Decay**: We don't notice a relationship is fading until it's gone.
-   **Recency Bias**: We overvalue the people we spoke to *today*, ignoring the best friend we haven't spoken to in a year.
-   **Data Opacity**: We have the data (timestamps), but no view that sorts by "Time Since Last Contact".

**The Opportunity**:
We can query the existing DuckDB database to generate a "Social Health Dashboard" in milliseconds.

---

## 3. Proposed Solution

**Goal**: Add a `Connection Health` section to the generated site (or a CLI command `egregora health`).

**Features**:
1.  **The "Ghost" List**: A table of authors sorted by `Days Since Last Message` (Descending).
2.  **Interaction Velocity**: A sparkline or metric showing "Messages per Year" for top contacts.
3.  **Eras**: Identify "Golden Ages" of interaction (e.g., "Peak: 2021").

**Output**:
A static Markdown page `connection_health.md` generated during the build process, accessible via the site navigation.

---

## 4. Value Proposition

| Metric | Improvement |
| :--- | :--- |
| **Awareness** | Instantly visualize which relationships are "Cold". |
| **Nostalgia** | Surprising rediscovery of forgotten friends ("Oh, I haven't talked to Mike in 4 years!"). |
| **Actionability** | A simple list of people to reach out to. |

---

## 5. BDD Acceptance Criteria

### Feature: Connection Health Calculation
```gherkin
Feature: Connection Health Report
  As a user
  I want to see who I haven't spoken to in a long time
  So that I can prioritize who to reach out to

  Scenario: Identifying "Cold" Connections
    Given the chat database contains messages from "Alice" (Last: 2023-01-01) and "Bob" (Last: 2025-01-01)
    And the current date is 2026-01-01
    When the Health Report is generated
    Then "Alice" should appear higher on the "Ghost List" than "Bob"
    And "Alice" should show "Silence: 3 Years"

  Scenario: Filtering "One-Offs"
    Given "Charlie" sent only 1 message in 2010
    When the Health Report is generated
    Then "Charlie" should be excluded or grouped under "Low Interaction"
    So that the report isn't cluttered with insignificant contacts
```

---

## 6. Implementation Plan (7 Days)

-   [ ] **Day 1-2**: Write the Ibis/DuckDB query to aggregate `(Author, Last_Seen, Msg_Count, First_Seen)`.
-   [ ] **Day 3-4**: Create a `HealthReport` data class and a Jinja template `health.md.jinja`.
-   [ ] **Day 5-6**: Integrate into the `write` pipeline (optional step enabled by flag `--report-health`).
-   [ ] **Day 7**: Testing and CSS polish.

**Success Metrics**:
-   Report accurately calculates `Days Since Last`.
-   Report renders cleanly in MkDocs.
