# RFC 035: The Entity Extractor (CLI Command)

**Status:** Proposed
**Type:** Quick Win ⚡
**Author:** Visionary (Jules)
**Date:** 2026-02-02
**Relation to Moonshot:** This is the **Ingestion/Data Cleaning** prerequisite for RFC 034.

## 1. Problem Statement

To build a Semantic Knowledge Graph (Moonshot), we first need to know *what* entities exist in the chat. Currently, Egregora is a black box. Users have no way to:
1.  See a list of all detected people/places.
2.  Identify duplicates ("Ally" vs "Alice").
3.  Audit what the system considers "important".

We need a way to **Extract and Audit** entities before we can **Graph** them.

## 2. Proposed Solution

Implement a new CLI command: `egregora extract entities`.

This command will:
1.  Parse the input (WhatsApp ZIP).
2.  Run a lightweight extraction pass (using `spacy` or a cheap LLM call on sampled windows).
3.  Output a structured JSON/Markdown report of top entities.

**Command Signature:**
```bash
egregora extract entities <INPUT_PATH> --limit 50 --format json --output entities.json
```

## 3. Value Proposition

- **Immediate Analytics:** "Who are the top 10 most mentioned people?" "What are our top 5 vacation spots?"
- **Data Hygiene:** Allows users to spot OCR errors or nicknames that need resolution *before* generating the full site.
- **Low Cost:** Can be done with local NLP libraries (Spacy) without expensive API calls.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Entity Extraction CLI
  As a Data Curator
  I want to extract and list entities from the chat logs
  So that I can audit the data and understand key topics

  Scenario: Extracting from WhatsApp ZIP
    Given a valid WhatsApp export "chat.zip" containing 1000 messages
    And the chat discusses "Alice", "Bob", and "Paris" frequently
    When I run `egregora extract entities chat.zip --limit 10`
    Then the process should complete successfully
    And the output should be a JSON list
    And "Alice" and "Bob" should be categorized as "PERSON"
    And "Paris" should be categorized as "GPE" (Geopolitical Entity)
    And each entity should have a frequency count > 0

  Scenario: Filtering by Entity Type
    Given the chat contains People and Locations
    When I run `egregora extract entities chat.zip --type PERSON`
    Then the output should ONLY contain entities of type "PERSON"
    And "Paris" should NOT be in the output

  Scenario: Performance (Time Limit)
    Given a chat with 10,000 messages
    When I run extraction
    Then it should complete in under 60 seconds (using local NLP)
```

## 5. Implementation Plan (30 Days)

- [ ] **Day 1-5:** Research & Prototyping. Test `spacy` vs `gliner` vs `LLM` for quality/speed trade-off.
- [ ] **Day 6-15:** Implementation. Create `src/egregora/knowledge/extraction.py` and the CLI command in `src/egregora/cli/extract.py`.
- [ ] **Day 16-20:** Integration Testing. Verify it works with WhatsApp adapters.
- [ ] **Day 21-25:** Output Formatting. Ensure JSON/Markdown outputs are clean.
- [ ] **Day 26-30:** Documentation & Release.

## 6. Success Metrics

- **Accuracy:** > 80% correct entity categorization (measured against manual sample).
- **Speed:** < 10ms per message.
- **Utility:** Users report finding "forgotten" people/places in their logs.
