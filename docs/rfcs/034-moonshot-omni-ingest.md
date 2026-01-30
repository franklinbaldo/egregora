# RFC 034: Egregora Omni-Ingest (Moonshot)

| Metadata | Value |
| :--- | :--- |
| **Title** | Egregora Omni-Ingest: The Universal Life Narrator |
| **Author** | Visionary (Jules) |
| **Status** | Proposed |
| **Type** | Moonshot |
| **Created** | 2026-02-01 |
| **Dependencies** | RFC 035 (Generic Adapter) |

## 1. Problem Statement

Egregora is currently a "WhatsApp Blog Generator". While powerful, this scope limits its potential to be a true "Life Narrator". Users communicate across Discord, Slack, Signal, Email, and voice memos. They schedule lives on Calendars and take notes in Obsidian.

By limiting ingestion to WhatsApp, we miss 80% of the user's digital footprint. The current assumption—"Input is a WhatsApp ZIP"—creates a rigid pipeline that resists expansion.

## 2. Proposed Solution: The Omni-Ingest Architecture

We propose transforming Egregora into a **Universal Ingestion Platform**.

Instead of a single "WhatsApp Adapter", we introduce a **Unified Event Stream**. All inputs (chat, email, calendar, location) are normalized into a common `LifeEvent` schema. The pipeline then narrates the *aggregate* of these events, finding correlations across platforms.

### Core Components:

1.  **The Universal Event Bus:** A standardized schema for any timestamped event (`Who`, `What`, `When`, `Where`, `Context`).
2.  **Plugin Ecosystem:** A modular system where `InputAdapters` are plugins. Community can write adapters for Discord, Gmail, Spotify history, etc.
3.  **Cross-Stream Context:** The RAG system is upgraded to query across streams. "Show me what I was listening to when I wrote this message."

## 3. Value Proposition

*   **For Users:** A single, searchable, narrated home for their *entire* digital life. "The Story of You," not just "The Story of Your Chats."
*   **For Developers:** A platform to build on. Writing a parser for "Telegram" becomes a small plugin, not a fork.
*   **For the AI:** Richer context means better profiles and better stories. Knowing you had a meeting with "John" explains why you messaged him later.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Multi-Source Narrative Construction
  As a user with a fragmented digital life
  I want to ingest data from multiple platforms (e.g., WhatsApp, Discord, Calendar)
  So that Egregora tells a complete, interconnected story

  Scenario: Interleaved Timeline Generation
    Given I have configured a WhatsApp source and a Discord source
    And both sources contain messages from the same date "2025-10-10"
    When the pipeline generates a post for "2025-10-10"
    Then the post should contain a chronological blend of messages from both sources
    And the narrative should explicitly bridge topics discussed on both platforms
    And the "Author Profiles" should merge identities (e.g., "Jules" on Discord = "Jules" on WhatsApp)

  Scenario: Cross-Context Retrieval (RAG)
    Given I have ingested my Calendar and my Chats
    When the "Writer" agent generates a summary of a conversation
    Then it should reference concurrent Calendar events (e.g., "This chat happened during the 'Project Kickoff' meeting")
    And the context score for the post should increase due to the correlation

  Scenario: Plugin Discovery
    Given a new "Slack Adapter" plugin is installed in `.egregora/plugins/`
    When I run `egregora adapters list`
    Then "Slack" should appear as a valid input source
    And I should be able to run `egregora write slack-export.zip`
```

## 5. Risks & mitigations

*   **Risk:** Schema complexity. Trying to fit everything into one schema might make it too generic.
    *   *Mitigation:* Use a flexible `payload` field in the schema (JSONB style) while enforcing strict core fields (timestamp, actor).
*   **Risk:** Privacy leakage. Aggregating *all* data increases the impact of a breach.
    *   *Mitigation:* Reinforce the "Local-First" architecture. Data never leaves the machine unless published.
*   **Risk:** Identity Resolution. Mapping "Jules" (Discord) to "@jules" (Slack) is hard.
    *   *Mitigation:* Introduce an explicit "Identity Mapping" config file or UI flow.

## 6. Implementation Hints

1.  **Phase 1 (RFC 035):** Build the `GenericInputAdapter` to prove the schema.
2.  **Phase 2:** Refactor `runner.py` to accept a list of adapters, not just one.
3.  **Phase 3:** Implement "Identity Merging" logic in the `Profile` agent.
4.  **Phase 4:** Build the Plugin Loader.
