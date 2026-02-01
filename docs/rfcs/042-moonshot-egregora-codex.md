# RFC 042: Egregora Codex (The Book of Knowledge)

**Status:** Proposed
**Type:** Moonshot 🔭
**Author:** Visionary (Jules)
**Date:** 2026-02-02

---

## 1. Problem Statement

**The Assumption**: "History is chronological."

Currently, Egregora formats chat logs as a **Blog**: a linear stream of posts organized by date. While this preserves the timeline, it destroys the **topology** of memory.

*   **Fragmentation**: A conversation about "Project X" in 2021 is completely disconnected from a conversation about "Project X" in 2024.
*   **Hidden Entities**: People, places, and concepts are trapped inside the text. You can search for them, but you cannot "visit" them.
*   **Context Loss**: Reading a single post gives you the text, but not the *web* of relationships surrounding it.

We are building a **Diary**, but what users actually need is an **Encyclopedia** of their life.

## 2. Proposed Solution: The Egregora Codex

We propose transforming the output format from a "Blog" to a **"Digital Codex"** (or Digital Garden). This treats the archive as a **Knowledge Graph** first, and a timeline second.

### Key Components

1.  **Concept Entities**:
    *   The system extracts "Concepts" (e.g., "The Lake House", "Startup Idea", "Mom's Health") and creates dedicated **Wiki Pages** for them.
    *   These pages aggregate every mention of the concept across all years, summarizing the evolution of the topic.

2.  **Bidirectional Linking (Backlinks)**:
    *   Every mention of a Concept or Person in a post automatically links to their Wiki Page.
    *   The Wiki Page lists all "Mentions" (Backlinks), allowing users to traverse the history of an idea.

3.  **Graph Visualization**:
    *   A visual node-link diagram showing how people and topics connect.
    *   "Who talks about 'Philosophy' the most?" -> The graph reveals the cluster.

4.  **The "Codex" View**:
    *   A new top-level section of the site (alongside "Journal") that serves as the index of all known entities, organized by category (People, Places, Events, Topics).

## 3. Value Proposition

*   **"The Obsidian That Writes Itself"**: Users get the power of a personal knowledge base (PKM) without the manual labor of tagging and linking.
*   **Deep Context**: Users can instantly see the entire history of a relationship or project, not just the latest update.
*   **Serendipity**: The Graph View reveals connections the user may have forgotten ("I didn't realize I talked about 'Japan' with both Alice and Bob!").

## 4. BDD Acceptance Criteria

```gherkin
Feature: Digital Codex (Wiki Structure)
  As a user exploring my history
  I want to navigate by Concept rather than just Date
  So that I can see the evolution of ideas and relationships

  Scenario: Concept Page Generation
    Given a recurring topic "Project Titan" appears in chats from 2020, 2021, and 2023
    When the Codex is generated
    Then a page "codex/topics/project-titan.md" should exist
    And it should contain a summary of the project
    And it should list "Mentions" linking back to the specific chat posts

  Scenario: Bidirectional Navigation
    Given I am reading a post from "2021-05-12"
    And the text mentions "Alice"
    When I click the link "Alice"
    Then I should be taken to "codex/people/alice.md"
    And "codex/people/alice.md" should list "2021-05-12" in its "Appears In" section

  Scenario: Graph Visualization
    Given the Codex has generated 50 entity pages
    When I visit the "Graph View" page
    Then I should see an interactive network graph
    And clicking a node should highlight its connections and link to the entity page
```

## 5. Implementation Hints

*   **Entity Extraction**: Enhance `EnrichmentWorker` to identify persistent topics (using LLM or TF-IDF across the corpus).
*   **Site Structure**: Move from `mkdocs-material`'s blog plugin to a custom structure or use `mkdocs-roamlinks-plugin` for backlink support.
*   **Graph Lib**: Use `d3.js` or `cytoscape.js` embedded in a custom Jinja template for the Graph View.

## 6. Risks

*   **Noise**: Too many links make text unreadable. **Mitigation**: Only link the *first* mention per section, or use "Smart Thresholding" (only link important entities).
*   **Hallucination**: The LLM might invent concepts. **Mitigation**: Strict grounding—only create entities that appear in >N distinct conversations.
*   **Performance**: Generating thousands of wiki pages increases build time. **Mitigation**: Incremental builds and lazy generation.
```
