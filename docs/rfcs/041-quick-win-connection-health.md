# 🔭 RFC 041: Connection Keepers (formerly The Ghost Report)

**Status**: Proposed
**Type**: Quick Win ⚡
**Driver**: Visionary
**Date**: 2026-02-02
**Reviewer**: Maya (User Advocate)

---

## 1. Relation to Moonshot (RFC 040)

The **Moonshot (Egregora Keeper)** envisions an active agent that prompts you to reconnect. This **Quick Win** builds the foundational *metrics* for that vision. Before we can "Nudge", we must first "Measure".

This RFC proposes a simple report that visualizes the state of your relationships in a supportive, non-guilt-inducing way.

---

## 2. Problem Statement

**The Assumption**: "Users lose touch with friends but don't know who to reach out to."

**The Friction**:
-   **Drifting Apart**: We often don't notice a relationship is fading until it's been years.
-   **Recency Bias**: We focus on the people we spoke to today, forgetting the best friend we haven't spoken to in a year.
-   **Hidden Treasures**: Our chat history contains data on who we used to be close with, but it's hidden in the archives.

**The Opportunity**:
We can generate a "Connection Keepers" page that highlights opportunities to reconnect.

---

## 3. Proposed Solution

**Goal**: Add a `Connection Keepers` section to the generated site.

**Features**:
1.  **Reconnect Opportunities** (formerly "Ghost List"): A list of close friends you haven't spoken to recently, framed as an opportunity.
2.  **Relationship Rhythms** (formerly "Interaction Velocity"): Visual sparklines showing the "heartbeat" of a conversation over time.
3.  **Golden Eras**: Identifying peak years of interaction (e.g., "The 2021 Era").

**UX Reference**:
See `docs/rfcs/041-mock-maya.md` for the desired visual tone.

**Output**:
A static Markdown page `connections.md` generated during the build process.

---

## 4. Value Proposition

| Metric | Improvement |
| :--- | :--- |
| **Awareness** | Gently reminds you of friends you might miss. |
| **Nostalgia** | Rediscover "Golden Eras" of friendship. |
| **Actionability** | Easy links to send a "Thinking of you" message. |

---

## 5. BDD Acceptance Criteria

### Feature: Connection Health Calculation
```gherkin
Feature: Connection Keepers Report
  As a user
  I want to see who I haven't spoken to in a long time
  So that I can prioritize who to reach out to without feeling guilty

  Scenario: Identifying Reconnect Opportunities
    Given the chat database contains messages from "Alice" (Last: 2023-01-01) and "Bob" (Last: 2025-01-01)
    And the current date is 2026-01-01
    When the Connection Report is generated
    Then "Alice" should appear as a "Reconnect Opportunity"
    And "Alice" should show "Last spoken: 3 Years ago"

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
