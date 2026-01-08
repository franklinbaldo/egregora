# RFC: The Living Document
**Status:** Moonshot Proposal
**Date:** 2024-07-26
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine that after a day of conversation, Egregora doesn't just generate a static blog post. Instead, a new page appears in the team's Notion or Google Docs workspace. This page contains the AI-generated summary, key decisions, and action items as usual. But at the bottom, there are two new sections: "Clarifications Needed" and "Human-in-the-Loop Edits."

A team member sees the summary and corrects a misinterpreted point directly on the page. Another adds a comment: "@Egregora, who was assigned to follow up on the 'Project Chimera' decision?"

The next time the pipeline runs, Egregora **reads this page first**. It ingests the human edits to refine its internal memory. It sees the comment and amends the document to clarify that "Alice" was assigned the follow-up task. The document is no longer a dead artifact; it's a shared, persistent, and evolving understanding between the team and their AI. The output has become an input, creating a virtuous feedback loop.

## 2. The Broken Assumption
This proposal challenges the most fundamental architectural assumption in Egregora Pure: **that the data pipeline is a one-way street (`Input -> Output`).**

> "We currently assume that the system's job is to produce a final, immutable artifact from a raw input. This forces the AI to be a passive archivist, forever looking at the past. This prevents us from creating a true symbiotic relationship where the AI can learn from human feedback and participate in the present."

## 3. The Mechanics (High Level)
*   **Input:** The system gains a new input source: the previously generated output document itself. We'll need a new type of `Adapter` (e.g., `NotionAdapter`, `GoogleDocsAdapter`) that can both read and write.
*   **Processing:**
    1.  **Read & Reconcile:** On each run, the agent first reads the existing "Living Document" for a given conversation window. It parses human edits, comments, and corrections, using this feedback to update its internal state or prompt context.
    2.  **Generate & Merge:** The agent then processes any *new* conversation data from the chat logs, as usual.
    3.  **Two-Way Sync:** Finally, it merges the new information with the reconciled human feedback and updates the Living Document in place, preserving human edits while adding new content.
*   **Output:** The primary output is no longer a collection of static files but a connection to a live, collaborative document service.

## 4. The Value Proposition
This transforms Egregora from a useful archivist into an indispensable team member.
- **From Static to Dynamic:** The knowledge base is no longer a point-in-time snapshot but a constantly improving source of truth.
- **Unlocks True Collaboration:** It creates a low-friction way for humans to correct, guide, and collaborate with the AI, making the final output dramatically more accurate and useful.
- **The Agent Gets a Memory:** By reading its own outputs and the feedback they receive, the agent develops a persistent memory and context that transcends individual pipeline runs. It learns from its mistakes.
