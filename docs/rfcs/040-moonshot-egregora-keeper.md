# 🔭 RFC 040: Egregora Keeper (The Relationship Cultivator)

**Status**: Proposed
**Type**: Moonshot 🔭
**Driver**: Visionary
**Date**: 2026-02-02

---

## 1. Problem Statement

**The Tragedy of Entropy**: Relationships degrade by default. Without energy input (messages, calls, meetings), the connection between two people weakens.
**The Tooling Gap**: Social networks (WhatsApp, Signal, Telegram) prioritize *recency*. If you stop talking to someone, they disappear from your feed, accelerating the decay.
**The Passive Archive**: Egregora currently treats chat logs as dead artifacts to be preserved. It fails to use this rich data to *sustain* the living relationships that generated it.

## 2. Proposed Solution

**Vision**: Transform Egregora from an **Archive** into a **Keeper**.

**The Keeper** is an autonomous agent responsible for the "Social Health" of the user. It does not just index the past; it uses the past to secure the future.

**Core Capabilities:**
1.  **Silence Detection**: Monitors the "Heartbeat" of every relationship. Identifies when a close friend is drifting away.
2.  **Contextual Nudges**: Generates low-friction conversation starters based on shared history.
    -   *Example*: "It's been 3 months since you spoke to Sam. You used to talk about 'Dune' a lot. Maybe send him this new trailer?"
3.  **Significant Date Inference**: Infers birthdays, anniversaries, and "friend-versaries" from the chat text (without manual entry) and reminds you.
4.  **The Reunion Protocol**: Detects when a group chat has died and suggests a "Spark" memory to revive it.

---

## 3. Value Proposition

| Metric | Improvement |
| :--- | :--- |
| **Relationship Retention** | Prevents "drift" by catching it early. |
| **Cognitive Load** | Offloads the mental tracking of "Who do I owe a call to?" |
| **Social Depth** | Moves interactions from "Happy Birthday" (generic) to "Remember this?" (specific). |
| **Differentiation** | Turns Egregora into a "Life Tool", not just a "Backup Tool". |

---

## 4. BDD Acceptance Criteria

### Feature: Silence Detection & Nudging
```gherkin
Feature: Relationship Nudging
  As a busy user
  I want to be reminded when close friends are drifting away
  So that I can reconnect before it's too late

  Scenario: Detecting a Fading Connection
    Given I have a history of 5000 messages with "Alice"
    But there have been 0 messages in the last 90 days
    When the Keeper runs its "Health Scan"
    Then it should flag "Alice" as "At Risk (Fading)"
    And it should generate a nudge: "You haven't spoken to Alice in 3 months."

  Scenario: Generating a Contextual Starter
    Given "Alice" is flagged as "At Risk"
    And our top shared topic in the past was "Coffee"
    When I request a "Reconnection Starter"
    Then the Keeper should suggest: "Hey Alice, had any good coffee lately? Reminds me of that place we went to in 2022."
```

### Feature: Significant Date Inference
```gherkin
Feature: Date Inference
  As a forgetful friend
  I want the system to remind me of birthdays without me entering them
  So that I never miss a celebration

  Scenario: Inferring a Birthday
    Given the chat log contains multiple messages saying "Happy Birthday!" to "Bob" on "June 14th" across different years
    When the Keeper analyzes "Bob"
    Then it should infer "Birthday: June 14" with High Confidence
    And it should schedule a reminder for June 14th
```

---

## 5. Implementation Hints

-   **Privacy First**: The Keeper runs locally. It never messages people *for* you. It only prompts *you*.
-   **Frequency Analysis**: Use `scikit-learn` or simple statistical heuristics to determine the "Natural Frequency" of a relationship (e.g., Daily vs Monthly) to avoid false positives.
-   **Agent**: A new `KeeperAgent` that runs periodically (or on demand via CLI).

## 6. Risks

-   **Guilt Induction**: Constant reminders of "failing" relationships can be stressful. **Mitigation**: "Quiet Mode" and smart filtering (only top 10 friends).
-   **False Positives**: Reminding me to call an ex-partner or a deceased friend. **Mitigation**: "Mute Person" feature is essential Day 1.
-   **Creepiness**: "How did you know my birthday?" **Mitigation**: Transparently show the source message ("Inferred from msg on 2021-06-14").
