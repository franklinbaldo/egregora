# RFC 035: Generic JSON Input Adapter (Quick Win)

| Metadata | Value |
| :--- | :--- |
| **Title** | Generic JSON Input Adapter: The Universal Key |
| **Author** | Visionary (Jules) |
| **Status** | Proposed |
| **Type** | Quick Win |
| **Created** | 2026-02-01 |
| **Target Delivery** | 30 Days |
| **Relation to Moonshot** | Foundational Step for RFC 034 (Omni-Ingest) |

## 1. Problem Statement

Adding support for a new platform (e.g., Discord) currently requires modifying the Egregora codebase to add a specific `InputAdapter`. This is a high barrier to entry. Users with technical skills who could script a conversion from their data to Egregora cannot do so because there is no "standard input format" exposed to them.

## 2. Proposed Solution

Implement a `GenericInputAdapter` that reads a standardized JSON (or JSONL) file.

**The Schema (`egregora-event.schema.json`):**
```json
{
  "events": [
    {
      "timestamp": "2025-10-10T14:00:00Z",
      "author": "Alice",
      "content": "Hello world!",
      "source": "discord",
      "thread_id": "channel-123",
      "attachments": ["image1.jpg"]
    }
  ]
}
```

If a user feeds this file to Egregora, the `GenericInputAdapter` converts it directly to the internal `Table` representation, bypassing platform-specific parsing.

## 3. Value Proposition

*   **Immediate Extensibility:** Instantly unlocks Discord, Slack, Telegram, Matrix, IRC, and Email support (via community scripts).
*   **Decoupling:** Allows the core pipeline to evolve independently of input parsers.
*   **Testing:** Makes it trivial to create mock data for integration tests.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Generic Data Ingestion
  As a developer or power user
  I want to import data via a standardized JSON format
  So that I can use Egregora with unsupported platforms without waiting for official adapters

  Scenario: Ingesting a valid JSON stream
    Given a file "custom_chat.json" containing 100 messages in the Egregora Schema
    And the messages span 3 distinct dates
    When I run `egregora write custom_chat.json`
    Then the pipeline should successfully parse the file
    And generate 3 blog posts (one for each date)
    And the author profiles should reflect the names in the "author" field

  Scenario: Handling Media Attachments
    Given the JSON input references a local image "party.jpg" in the "attachments" field
    And the file "party.jpg" exists in the same directory
    When the pipeline processes the message
    Then the generated post should include an embedded image `![party.jpg](...)`
    And the image should be copied to the site's media asset folder

  Scenario: Schema Validation Failure
    Given a JSON file with missing "timestamp" fields
    When I run `egregora write invalid.json`
    Then the CLI should exit with a clear validation error
    And show which record failed validation
```

## 5. Implementation Plan (30 Days)

| Step | Task | Estimate |
| :--- | :--- | :--- |
| **1** | **Define Schema:** Create Pydantic model for `GenericEvent` and generate JSON Schema. | 3 Days |
| **2** | **Implement Adapter:** Create `src/egregora/input_adapters/generic.py`. | 5 Days |
| **3** | **CLI Integration:** Update `registry.py` to auto-detect JSON files or add `--format json`. | 2 Days |
| **4** | **Documentation:** Write "How to import custom data" guide with example scripts (e.g., Discord->JSON). | 5 Days |
| **5** | **Verification:** Add E2E tests using the JSON adapter. | 5 Days |
| **Buffer** | Code Review & Refinement | 10 Days |

## 6. Success Metrics

*   **Functionality:** 100% of the BDD scenarios pass.
*   **Adoption:** At least 1 community-created script (e.g., Discord exporter) appears within 30 days of release.
*   **Performance:** Parsing 10MB JSON file takes <5 seconds.
