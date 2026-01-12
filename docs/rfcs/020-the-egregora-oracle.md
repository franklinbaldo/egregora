# RFC: 020 - The Egregora Oracle
**Status:** Moonshot Proposal
**Date:** 2024-07-29
**Disruption Level:** High

## 1. The Vision
Imagine a conversation where your group's knowledge is no longer bounded by its own experience. When discussing a new competitor, a relevant news article appears. When planning a trip, a summary of the best local restaurants is automatically provided. This is the vision of the **Egregora Oracle**. It's a proactive agent that listens to the conversation, identifies knowledge gaps, and autonomously searches the external world (the web, APIs, etc.) to find and inject the missing context. It transforms Egregora from a simple *group memory* into a powerful *collective intelligence*—an augmented mind for the group.

## 2. The Broken Assumption
This proposal challenges the assumption that **Egregora is a closed system.**
> "We currently assume that the only source of truth is the chat log itself. This prevents us from enriching conversations with real-time, external information, limiting the group's perspective to what it already knows."

By breaking this assumption, we evolve Egregora from a passive archivist of internal knowledge into an active curator of external wisdom.

## 3. The Mechanics (High Level)
*   **Input:** The real-time stream of chat messages.
*   **Processing:**
    1.  **Intent Recognition:** The Oracle uses an LLM to analyze the conversation and detect "knowledge-seeking moments" (e.g., questions, mentions of unknown topics, planning activities).
    2.  **Autonomous Research:** When a moment is detected, the agent formulates a search query, executes it against a web search API, and reads the top results.
    3.  **Synthesis & Caching:** The agent synthesizes the search results into a concise summary and permanently archives the source material (the article content) within its own knowledge base (LanceDB), making it available for future RAG queries.
*   **Output:** A real-time message posted back to the chat, containing the synthesized answer and a link to the archived source. Example: "I noticed you're talking about Project X. I found a recent article about their funding round. Here's a summary..."

## 4. The Value Proposition
This shift dramatically increases the value and utility of Egregora.
- **Breaks Knowledge Bubbles:** It prevents groupthink by systematically introducing new, external information and perspectives.
- **Automates Tedious Work:** It saves users the manual effort of context-switching to a browser, searching, and pasting links. The cognitive load of research is outsourced to the agent.
- **Creates a Permanent, Enriched Archive:** The knowledge base is no longer just a record of conversations; it becomes a curated library of the external resources that informed those conversations, making the archive exponentially more valuable over time.
