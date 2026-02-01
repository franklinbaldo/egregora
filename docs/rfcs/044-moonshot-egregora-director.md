# RFC 044: Egregora Director (Co-Creative Pipeline)

- **Author**: Visionary Persona
- **Date**: 2026-02-02
- **Status**: Proposed
- **Type**: Moonshot 🔭
- **Ladder**: Built upon [RFC 045 (Story Scout)](./045-quick-win-story-scout.md)

## 1. Problem Statement

Currently, Egregora operates as a **"Black Box" batch process**.
1.  User runs `egregora write`.
2.  System churns for minutes/hours.
3.  System outputs a static site.

**The Friction**:
-   **No Agency**: Users cannot influence *what* stories are told or *how* they are told.
-   **Blind Spots**: The fixed time-windowing strategy often chops narrative arcs in half or merges unrelated events.
-   **Edit Latency**: To fix a bad story, the user must edit the raw Markdown or hack complex prompts, which breaks the "Magic by Default" promise.

We are treating the user as a **consumer** of the output, not a **co-creator**.

## 2. Proposed Solution: Egregora Director

We propose a new **Human-in-the-Loop (HITL) workflow** that transforms the batch pipeline into an interactive creative session.

The new workflow consists of 4 phases:

1.  **Analyze (The Scout)**: The system scans the chat history and uses clustering/embeddings to identify potential "Story Arcs" (e.g., "The Japan Trip", "The Pizza Debate").
2.  **Pitch (The Meeting)**: The system presents these arcs to the user via an interactive Terminal UI (TUI).
    -   *"I found 3 major stories in this period. Which ones should we write?"*
3.  **Direct (The Brief)**: The user provides high-level direction for selected arcs.
    -   *"Keep it funny."*
    -   *"Focus on the photos."*
    -   *"Merge these two threads."*
4.  **Generate (The Writer)**: The system executes the writing process based on the approved briefs.

## 3. Value Proposition

*   **Higher Quality**: Stories are curated by humans, eliminating "noise" and focusing on "signal".
*   **Narrative Integrity**: Dynamic windowing (based on arcs) replaces rigid time-based windowing.
*   **User Engagement**: Turns the "waiting time" into a "creative time".
*   **Personalization**: The blog reflects the user's *intent*, not just the model's *inference*.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Interactive Director Workflow

  As a user who wants to curate my chat history
  I want to review and direct story generation
  So that the final blog reflects the most meaningful memories

  Scenario: The Pitch Meeting
    Given I have a chat export with a "Road Trip" event
    When I run `egregora director start`
    Then the system should analyze the history
    And it should present a "Pitch: Road Trip to Vegas (45 messages)"
    And it should ask "Do you want to produce this story? [Y/n]"

  Scenario: Giving Direction
    Given I have accepted the "Road Trip" pitch
    When the system asks for "Director Notes"
    And I enter "Focus on the flat tire incident"
    Then the generated blog post should include the "flat tire" details
    And the post tone should reflect the direction

  Scenario: Merging Arcs
    Given the system proposes "Dinner Friday" and "Breakfast Saturday" as separate arcs
    When I select both and choose "Merge"
    Then the system should generate a single post covering both events
    And the title should reflect the combined scope
```

## 5. Implementation Hints

*   **TUI**: Use `Textual` or `Rich` for the interactive "Pitch Meeting" interface.
*   **State Management**: We need a `DirectorSession` object to store the user's decisions before passing them to the `WriterAgent`.
*   **Arc Detection**: Relies on the clustering logic defined in **RFC 045 (Story Scout)**.
*   **Prompting**: Update `writer.jinja` to accept "Director Notes" as a system instruction override.

## 6. Risks

*   **Fatigue**: Users might not *want* to do work. The "Batch Mode" must remain the default (or a "Auto-Approve" option).
*   **Complexity**: Managing state between the "Analyze" and "Generate" phases adds architectural complexity to the stateless `orchestration` layer.
*   **Cost**: "Analyze" phase requires embedding all messages, which has a cost (though `lancedb` is local/cheap, embedding APIs are not).
