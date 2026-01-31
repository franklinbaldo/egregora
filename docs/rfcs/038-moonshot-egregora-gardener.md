# RFC 038: Egregora Gardener (The Self-Healing Archive)

**Status:** Draft
**Type:** Moonshot 🚀
**Author:** Visionary (Jules)
**Date:** 2026-01-29

---

## 1. Problem Statement

Current archives are static. Once Egregora generates a blog post from a chat export, that content is frozen in time. However, the world changes:
*   **Link Rot**: External URLs referenced in chats die (404).
*   **Context Drift**: "The President" means someone different in 2015 vs 2025.
*   **Entity Fragmentation**: A user might be saved as "Mom" in one export and "Mother" in another, creating disconnected profiles.
*   **Data Quality**: OCR errors, typos, and formatting glitches remain forever.

A "Memory" that decays is not a good memory. Egregora currently lacks a mechanism to revisit and refine existing data.

## 2. Proposed Solution

Introduce **The Egregora Gardener**: an autonomous, background agent framework dedicated to the continuous maintenance and improvement of the archive. Unlike the `Writer` (who creates new content) or the `Reader` (who consumes it), the `Gardener` tends to the existing data.

The Gardener runs on a schedule (e.g., weekly) and performs specific "Pruning" and "Grafting" tasks:
1.  **Rot Repair**: Checks for broken links and attempts to replace them with [Internet Archive](https://archive.org) snapshots.
2.  **Entity Unification**: Identifies duplicate profiles (fuzzy matching names/metadata) and merges them.
3.  **Context Backfill**: Enhances old posts with retrospective data (e.g., adding historical weather or stock prices to a "remember that storm?" chat).
4.  **Typo/Format Fixing**: Uses LLMs to correct obvious OCR or typo errors in the *presentation* layer (preserving the raw original).

## 3. Value Proposition

*   **Longevity**: Ensures the archive remains useful and navigable for decades, not just years.
*   **Coherence**: Unifies fragmented identities into single, rich profiles.
*   **Zero-Maintenance**: Users don't need to manually fix broken links or organize tags.
*   **"Living" System**: Transforms Egregora from a static generator into a dynamic Operating System for memory.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Self-Healing Archive (The Gardener)
  As a user with a long-term chat archive
  I want the system to automatically fix broken links and merge duplicate entities
  So that my memories remain accessible and organized without manual work

  Scenario: Repairing a broken link (Rot Repair)
    Given a chat message from 2015 containing "http://example.com/cool-meme"
    And the URL "http://example.com/cool-meme" now returns 404
    When the Gardener runs the "Rot Repair" task
    Then it should query the Internet Archive for a snapshot near the message date
    And it should update the post to link to the archived snapshot
    And it should tag the link as "Archived (Auto-repaired)"

  Scenario: Merging duplicate entities (Entity Unification)
    Given two profiles: "Mom" (ID: 123) and "Mother" (ID: 456)
    And both profiles share the same phone number or high semantic similarity
    When the Gardener runs the "Entity Unification" task
    Then it should flag them as "Potential Duplicate"
    And it should generate a merge proposal for the user
    # Or auto-merge if confidence is > 99%

  Scenario: Backfilling historical context
    Given a message discussing "the storm" on "2018-02-15"
    When the Gardener runs the "Context Backfill" task
    Then it should identify "storm" as a weather event
    And it should fetch historical weather data for that date/location
    And it should append a "Context Note: Heavy rain recorded (25mm)" to the metadata
```

## 5. Implementation Hints

*   **Agent Framework**: Extend `src/egregora/agents/` with a `gardener.py`.
*   **Task Queue**: Use the existing `task_store` to schedule recurrent maintenance jobs.
*   **Wayback Machine API**: Use `internetarchive` Python library for link checking/repair.
*   **Fuzzy Matching**: Use `TheFuzz` or vector similarity (LanceDB) for entity resolution.

## 6. Risks

*   **Destructive Edits**: Auto-merging the wrong people is catastrophic. **Mitigation**: "Propose, Don't Commit" for high-stakes changes (Require user confirmation via CLI or UI).
*   **Resource Usage**: Scanning thousands of links can be slow and expensive. **Mitigation**: Rate limiting and incremental scanning (one year per run).
*   **Privacy**: External API calls (Wayback Machine) leak which URLs you are checking. **Mitigation**: Optional feature, privacy warning.
```
