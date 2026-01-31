# 🔭 RFC 034: Egregora Biographer (The Active Archivist)

**Status**: Proposed
**Type**: Moonshot 🔭
**Driver**: Visionary
**Date**: 2026-01-30

---

## 1. Problem Statement

**The Assumption**: "The Archive is a passive bucket for data users choose to save."

**The Friction**:
-   **Unknown Gaps**: Users often realize years later that key periods (e.g., "Summer 2024") are missing from the archive because they forgot to export chats or take photos.
-   **Lack of Context**: A photo from 2010 might have no caption. The people who know the context (grandparents) are aging.
-   **Silent Failure**: The archive "succeeds" technically (files are stored) but fails functionally (the story is incomplete).

**The Opportunity**:
Egregora has the intelligence (LLM) to "read" the archive. It should detect narrative holes and *proactively* ask the user to fill them while the memory is fresh.

---

## 2. Proposed Solution

**Vision**: Transform Egregora from a "Storage Engine" to an **"Active Biographer"**.

The **Biographer Agent** runs periodically (or after ingestion) and performs two tasks:

1.  **Gap Hunter**: Scans the timeline for anomalies.
    -   *Temporal Gaps*: "You have 500 messages/month in 2023, but 0 in July 2023. Why?"
    -   *Narrative Gaps*: "You talk about 'The Project' for 6 months, but there is no conclusion. Did it finish?"
    -   *Visual Gaps*: "This week was tagged 'Vacation', but there are no photos."

2.  **The Interviewer**: Generates a daily/weekly prompt for the user via CLI, Email, or Web UI (Egregora Live).
    -   "Hey, I noticed a gap in July 2023. Was that when you moved house?"
    -   "Here is a photo from 2015 with unidentified people. Can you name them?"

The user's answers are ingested as new "Oral History" documents, filling the gaps.

---

## 3. Value Proposition

| Feature | Value |
| :--- | :--- |
| **Completeness** | Ensures the archive captures the *whole* story, not just the digital exhaust. |
| **Context Recovery** | Rescues lost details (names, places) before they are forgotten. |
| **Engagement** | Turns "archiving" (a chore) into "reminiscing" (a joy). |
| **Legacy** | Creates a robust history for future generations. |

---

## 4. BDD Acceptance Criteria

### Feature: Gap Hunter
```gherkin
Feature: Gap Hunter
  As a user who wants a complete history
  I want the system to tell me what I missed
  So that I can fill in the blanks

  Scenario: Detecting a temporal gap
    Given the timeline has average activity of 50 messages/day
    And there is a period of 0 messages for > 14 days
    When the Biographer runs
    Then it should flag this period as a "Temporal Gap"
    And it should generate a question: "What happened between [Start] and [End]?"

  Scenario: Detecting an unresolved narrative
    Given a topic "Renovation" has high sentiment and volume
    And the topic disappears abruptly without a "Conclusion" event
    When the Biographer runs
    Then it should ask: "How did the Renovation project end?"
```

### Feature: The Interview
```gherkin
Feature: The Interview
  As a user with limited time
  I want to answer specific questions
  So that I can enrich the archive efficiently

  Scenario: Ingesting an answer
    Given the system asked "What happened in July 2023?"
    When I reply "We went to Italy and I lost my phone."
    Then the system should create a new "Oral History" document
    And the timeline for July 2023 should now include this context
    And the "Temporal Gap" flag should be resolved
```

---

## 5. Risks & Mitigation

-   **Risk**: **Annoyance**. Users might hate being nagged.
    -   *Mitigation*: "Quiet Mode" by default. Only ask 1 question per session. Gamify the process ("Archive 95% complete").
-   **Risk**: **Privacy**. "Reading" messages to find gaps feels intrusive.
    -   *Mitigation*: All analysis runs locally. No data leaves the device (unless using Cloud LLM, which is opt-in per RFC 033).
-   **Risk**: **Hallucination**. The AI might invent gaps that don't exist.
    -   *Mitigation*: Use statistical analysis (Ibis/DuckDB) for temporal gaps first. Use LLM only for narrative gaps.

## 6. Implementation Hints

-   **Phase 1 (Stats)**: Implement `GapDetector` using Ibis to find zero-volume periods.
-   **Phase 2 (Questions)**: Create `InterviewerAgent` that takes a Gap and generates a polite question.
-   **Phase 3 (Ingestion)**: Create a new Input Adapter for `type: oral_history`.
