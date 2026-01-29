# 🔭 RFC 032: Egregora Live (The Living Archive Engine)

**Status**: Proposed
**Type**: Moonshot 🔭
**Driver**: Visionary
**Date**: 2026-01-26

---

## 1. Problem Statement

**The Assumption**: "Egregora's output is a static HTML site generated in batch mode."

**The Friction**:
-   **High Latency**: Users must wait for the entire pipeline (10-30 mins) to see *any* result.
-   **Dead Ends**: Once generated, the content is frozen. Users cannot ask follow-up questions ("What else did we say about this?") or pivot views dynamically (e.g., "Show only photos from 2023").
-   **Read-Only**: The archive is a museum, not a conversation partner. It fails to leverage the "Author Profiles" for simulation or interaction.

**The Opportunity**:
We have the data (DuckDB), the brains (Writer/Profile Agents), and the memory (RAG). We are limiting them by forcing them into a static `mkdocs build`.

---

## 2. Proposed Solution

**Vision**: Transition Egregora from a "Static Site Generator" to a **"Local Personal Intelligence Server"**.

Instead of just `egregora write`, we introduce `egregora serve --live`. This launches a lightweight local web server (FastAPI + HTMX) that provides:

1.  **Interactive RAG Chat**: A chat interface where you can talk *to* your archive.
    -   *User*: "When did we first talk about buying a house?"
    -   *Egregora*: "You first mentioned it in Nov 2023... [Links to posts]"
2.  **Dynamic Exploration**: Real-time filtering of the timeline by Author, Tag, Sentiment, or Media type.
3.  **The "Echo" Interface**: Interact with simulated profiles.
    -   *User*: "@Dad, what would you say about this game?"
    -   *Egregora (Simulating Dad)*: "Well, back in my day..." (Based on Profile DNA)

**Architecture Shift**:
-   **Current**: `Pipeline -> DuckDB -> Markdown -> MkDocs -> HTML`
-   **New**: `Pipeline -> DuckDB/LanceDB <-> API Layer <-> Dynamic UI`

---

## 3. Value Proposition

| Feature | Value |
| :--- | :--- |
| **Instant Gratification** | Start exploring data *while* it indexes, don't wait for batch completion. |
| **Deep Retrieval** | Ask complex questions that static tags can't answer. |
| **Emotional Connection** | "Echo" brings profiles to life, turning data into digital presence. |
| **Data Sovereignty** | A true "Personal Google" for your social history, running locally. |

---

## 4. BDD Acceptance Criteria

### Feature: Interactive Archive Chat
```gherkin
Feature: Interactive Archive Chat
  As a nostalgic user
  I want to ask natural language questions to my archive
  So that I can find memories without knowing the exact keywords

  Scenario: Retrieval of specific memory
    Given the archive contains a discussion about "Pizza" in 2023
    When I ask "What was the best pizza we had?"
    Then the system should return a summary based on the "Pizza" discussion
    And it should provide citations/links to the original messages

  Scenario: Profile-based simulation (The Echo)
    Given an Author Profile exists for "Alice" with high "Sarcasm" traits
    When I ask "@Alice, what do you think of this plan?"
    Then the system should generate a response mimicking Alice's style
    And the response should be tagged as "Simulated"
```

### Feature: Dynamic Timeline Filtering
```gherkin
Feature: Dynamic Timeline Filtering
  As a power user
  I want to filter the timeline instantly
  So that I can analyze specific trends

  Scenario: Filtering by Sentiment
    Given the archive has 1000 posts
    When I apply a filter "Sentiment: Joy"
    Then the UI should update in < 200ms
    And only posts with positive sentiment should be visible

  Scenario: Media Gallery View
    Given the archive contains images and videos
    When I switch to "Gallery Mode"
    Then I should see a grid of media items
    And clicking an item should show its context in the chat
```

---

## 5. Risks & Mitigation

-   **Risk**: **Resource Intensity**. Running a local LLM/Server might be heavy.
    -   *Mitigation*: Keep the "Server" lightweight (FastAPI). Offload LLM to provider (OpenAI/Google) or optional local Ollama.
-   **Risk**: **Privacy Perception**. "Server" sounds like "Cloud".
    -   *Mitigation*: Explicit branding as "Local Server". Clear UI indicators that no data leaves localhost (unless using cloud LLM).
-   **Risk**: **Scope Creep**. Building a UI is hard.
    -   *Mitigation*: Use HTMX for server-side rendering simplicity. Reuse existing MkDocs CSS/Theme where possible, or embed the Dynamic App *inside* MkDocs via iframe/JS.

## 6. Implementation Hints

-   **Phase 1**: Add `egregora-server` (FastAPI) that exposes DuckDB/LanceDB via REST API.
-   **Phase 2**: Build a simple Chat UI using Streamlit or NiceGUI (Python-native UIs) for rapid prototyping.
-   **Phase 3**: Integrate "Echo" simulation using existing `ProfileAgent`.
