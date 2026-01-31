# 🔭 RFC 035: Hologram (Synthetic History Generator)

**Status**: Proposed
**Type**: Quick Win ⚡
**Driver**: Visionary
**Date**: 2026-01-30

---

## 1. Relation to Moonshot (RFC 034)

The **Moonshot (Egregora Biographer)** relies on sophisticated logic to detect gaps and anomalies in chat history. To build and test this logic safely, we need a way to **simulate** those gaps without using private user data.

**Hologram** is the engine that generates these "Alternate Realities"—synthetic WhatsApp logs that are statistically and narratively consistent, allowing us to train the Biographer on controlled datasets.

---

## 2. Problem Statement

**The Assumption**: "We must use real user data for testing and demos."

**The Friction**:
-   **Privacy Barriers**: We cannot commit real WhatsApp logs to the repo. CI/CD runs on limited mock data.
-   **Edge Case Difficulty**: Finding real data that has *exactly* the edge case we want (e.g., "A 3-month gap followed by a breakup") is hard.
-   **Demo Limitations**: Demos look generic because we can't show "rich" personal history without violating privacy.

**The Opportunity**:
Use the existing `WriterAgent` infrastructure in reverse. Instead of `Chat -> Blog`, we go `Prompt -> Chat`.

---

## 3. Proposed Solution

**Goal**: Implement `egregora simulate`, a CLI tool to generate synthetic WhatsApp ZIP exports.

**Features**:
1.  **Scenario Scripting**: Define the "Arc" of the history.
    -   `--topic "Family Vacation"`
    -   `--mood "Chaotic but loving"`
    -   `--length "500 messages"`
2.  **Gap Injection**: Intentionally skip dates to test Gap Detection.
    -   `--gap "2023-07-01 to 2023-07-15"`
3.  **Persona Injection**: Use existing `.team/personas` or define new ones on the fly.

**Command**:
```bash
egregora simulate \
  --scenario "planning_trip.yaml" \
  --output "tests/fixtures/synthetic/trip_gap.zip"
```

---

## 4. Value Proposition

| Metric | Improvement |
| :--- | :--- |
| **Test Coverage** | Enables true E2E testing of complex narrative logic. |
| **Privacy** | Zero risk of leaking PII in demos or screenshots. |
| **Velocity** | Developers can generate test cases in seconds, not hours of hunting for data. |

---

## 5. BDD Acceptance Criteria

### Feature: Synthetic Generation
```gherkin
Feature: Synthetic History Generation
  As a developer
  I want to generate fake chat logs
  So that I can test the system without privacy risks

  Scenario: Generating a basic conversation
    Given a scenario "Argue about Pizza"
    And participants "Alice, Bob"
    When I run `egregora simulate`
    Then it should produce a valid `_chat.txt` file
    And the content should mention "Pizza"
    And the message count should be within 10% of target

  Scenario: Injecting a Gap
    Given a scenario requesting a gap from "2024-01-01" to "2024-02-01"
    When I run the simulation
    Then the output should contain NO messages in that date range
    And the surrounding messages should exist
```

### Feature: Persona Consistency
```gherkin
Feature: Persona Consistency
  As a demo creator
  I want the fake users to sound distinct
  So that the demo looks realistic

  Scenario: Distinct Voices
    Given "Alice" is defined as "Formal"
    And "Bob" is defined as "Slang-heavy"
    When the simulation runs
    Then Alice's messages should have higher avg length and proper grammar
    And Bob's messages should contain slang terms
```

---

## 6. Implementation Plan (21 Days)

-   [ ] **Day 1-5**: Create `SimulatorAgent` (a reversed WriterAgent).
-   [ ] **Day 6-10**: Implement `WhatsAppSerializer` to convert text back to the specific export format.
-   [ ] **Day 11-15**: Add "Director Mode" (Scenario configuration loader).
-   [ ] **Day 16-21**: Integrate with `egregora` CLI and verify against existing parsers.

**Success Metrics**:
-   Generated ZIPs are successfully parsed by `egregora write`.
-   Profiles generated from synthetic data match the input personas.
