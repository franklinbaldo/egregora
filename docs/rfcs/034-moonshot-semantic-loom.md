# RFC 034: The Semantic Loom (Egregora Knowledge Graph)

**Status:** Proposed
**Type:** Moonshot 🔭
**Author:** Visionary (Jules)
**Date:** 2026-02-02

## 1. Problem Statement

Current RAG (Retrieval-Augmented Generation) implementations, including Egregora's, rely on **Vector Similarity**. This is excellent for finding "text that sounds like query X", but fails at **Structured Reasoning**.

**The Friction:**
If a user asks: *"Who attended the camping trip in 2023?"*
- **Vector Search** finds messages like *"The camping trip was fun!"* or *"I loved the fire."*
- **The LLM** has to guess who "I" is, or hallucinate attendees based on proximity.
- **The Result:** Fuzzy, incomplete, or incorrect answers. It cannot definitively list participants or connect disjointed conversations about the same event.

We are treating "Context" as **Unstructured Text**, when it is actually **Implicit Knowledge**.

## 2. Proposed Solution: The Semantic Loom

We will implement a **Knowledge Graph (GraphRAG)** architecture.

Instead of just embedding chunks of text, we will use an LLM during ingestion to extract **Triplets**:
`Subject` --`PREDICATE`--> `Object`

**Examples:**
- `Alice` --`PARTICIPATED_IN`--> `Camping Trip 2023`
- `Camping Trip 2023` --`LOCATED_AT`--> `Yosemite`
- `Bob` --`MENTIONED`--> `Alice`

This "Semantic Loom" weaves individual messages into a queryable graph of facts.

### Key Components:
1.  **Graph Store:** A lightweight local graph database (e.g., KuzuDB or NetworkX over SQLite).
2.  **Extraction Agent:** A new `EntityExtractionAgent` that runs during the "Windowing" phase to harvest triplets.
3.  **Graph-Enhanced Retrieval:** When answering a query, we traverse the graph to find connected entities *before* performing vector search.

## 3. Value Proposition

1.  **Precision:** Deterministic answers to "Who", "Where", and "When" questions.
2.  **Deep Discovery:** Enable queries like "Show me all events Alice and Bob attended together" (impossible with vector search).
3.  **Visualization:** Generate visual social graphs for the static site.
4.  **Foundation for Digital Twin:** This structured memory is required for the "Living Biographer" vision (2031).

## 4. BDD Acceptance Criteria

```gherkin
Feature: Semantic Knowledge Graph
  As a curious user
  I want the system to understand relationships between entities
  So that I get precise answers to factual questions about our history

  Scenario: Complex Event Query
    Given the chat history contains scattered references to "The 2023 Road Trip"
    And "Alice" said "I'll bring the snacks for the road trip"
    And "Bob" said "Driving to the road trip now"
    When I ask "Who went on the 2023 Road Trip?"
    Then the system should identify "2023 Road Trip" as a specific Event node
    And traverse "PARTICIPATED_IN" edges
    And return a precise list: "Alice, Bob"
    And NOT include "Charlie" who only asked "How was the road trip?"

  Scenario: Contradiction Detection
    Given "Alice" said "I hate sushi" in 2021
    And "Alice" said "I love sushi now" in 2024
    When I ask "Does Alice like sushi?"
    Then the system should trace the "HAS_PREFERENCE" edges over time
    And explain the evolution: "Alice used to hate sushi (2021) but expressed love for it in 2024."

  Scenario: Implicit Connection
    Given "Alice" is connected to "Project X"
    And "Project X" is connected to "Bob"
    When I ask "How are Alice and Bob connected?"
    Then the system should find the path: "Alice --WORKED_ON--> Project X <--MANAGED_BY-- Bob"
```

## 5. Implementation Hints

- **Phase 1 (Ingestion):** Use `gliner` or a small LLM to extract entities/relations from windows.
- **Phase 2 (Storage):** Store as edge list in DuckDB (since we already use it) or a specialized store like Kuzu.
- **Phase 3 (Retrieval):** Implement "Hybrid Search" (Vector + Graph traversal) in `src/egregora/rag/`.

## 6. Risks

- **Extraction Cost:** Extracting triplets from every message is token-expensive.
  - *Mitigation:* Only run on high-perplexity windows or use smaller local models (spacy/gliner).
- **Entity Resolution:** "Ally" vs "Alice".
  - *Mitigation:* RFC 035 (Entity Extractor) is the prerequisite to solve this.
