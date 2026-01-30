# RFC 035: Generic JSON Adapter (Quick Win)

## 🔭 Vision
**Title:** Generic JSON Adapter
**Author:** Visionary (Jules)
**Status:** Draft
**Type:** Quick Win
**Relation to Moonshot:** This is the *first implementation* of the Omni-Ingest vision. By defining a JSON schema, we create the first "Universal Protocol" endpoint.

---

## 1. Problem Statement
**The Pain:** To get data into Egregora today, you must have a supported export format (currently only WhatsApp and a legacy court format). If you have a JSON dump from Discord or a CSV from Telegram, you are blocked unless you write Python code to implement `InputAdapter`.

**The Solution:** Create a "Universal Adapter" that accepts a standardized JSON format. If you can convert your data to JSON, you can use Egregora.

---

## 2. Proposed Solution

Implement `GenericJsonAdapter` in `src/egregora/input_adapters/json/adapter.py`.

### The JSON Schema (v1)
```json
[
  {
    "timestamp": "2023-10-27T10:00:00Z",
    "author": "Alice",
    "content": "Hello world!",
    "media": [
      {
        "path": "images/photo.jpg",
        "type": "image"
      }
    ],
    "reply_to": null
  },
  {
    "timestamp": "2023-10-27T10:01:00Z",
    "author": "Bob",
    "content": "Hi Alice!",
    "reply_to": 0  // Index or ID reference
  }
]
```

### Implementation Details
- **Adapter Name:** `json`
- **Input:** A single `.json` file or a `.zip` containing a `messages.json` and media files.
- **Logic:**
  1. Load JSON (streamed if large, using `ijson` or similar if needed, or just standard `json` for MVP).
  2. Normalize timestamps to UTC.
  3. Convert to Ibis Table.
  4. Handle media references by looking in the ZIP or relative path.

---

## 3. Value Proposition
- **Immediate Unblocking:** Users can now script their own converters in any language (Node, Go, Rust) to target Egregora.
- **Testing:** We can generate synthetic test data easily without needing complex WhatsApp mock exports.
- **Future Proofing:** This JSON format becomes the de-facto "Import API" for Egregora.

---

## 4. BDD Acceptance Criteria

```gherkin
Feature: Generic JSON Ingestion
  As a developer with non-WhatsApp data
  I want to feed a standardized JSON file to Egregora
  So that I can generate narratives from any source

  Scenario: Ingesting a Valid JSON List
    Given a file "chat.json" containing:
      """
      [
        {"timestamp": "2024-01-01T12:00:00", "author": "Me", "content": "Test"}
      ]
      """
    When I run "egregora write chat.json --adapter json"
    Then the pipeline accepts the data
    And the generated post contains "Test"
    And the author is identified as "Me"

  Scenario: Handling Missing Fields
    Given a JSON entry is missing the "timestamp" field
    When I attempt ingestion
    Then the adapter raises a SchemaValidationError
    And provides a helpful error message pointing to the invalid entry

  Scenario: Automatic Detection
    Given a file named "export.json"
    When I run "egregora write export.json"
    Then the system automatically selects the "json" adapter
```

---

## 5. Implementation Plan (≤30 Days)

- **Day 1-2**: Define Pydantic model for the JSON Schema.
- **Day 3-5**: Implement `GenericJsonAdapter` class.
- **Day 6-7**: Add unit tests and sample JSON files.
- **Day 8**: Register adapter in `pyproject.toml`.
- **Day 9-10**: Documentation and "How to write a converter" guide.

**Total Effort:** ~2 weeks (well within Quick Win limits).

---

## 6. Success Metrics
- **Usage:** At least 1 community converter (e.g., "Discord to Egregora JSON") created within 30 days of release.
- **Reliability:** 100% of valid JSON files pass ingestion tests.
