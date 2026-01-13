# RFC: The Decision Ledger
**Status:** Moonshot Proposal
**Date:** 2026-01-13
**Disruption Level:** High

## 1. The Vision
Imagine Egregora's primary output is no longer a blog, but a structured, auditable **Decision Ledger**. This ledger is a clean, minimalist, machine-readable log of every significant decision, action item, and commitment made in the group's conversations. It answers the most critical questions for any project or team: "What did we decide?" and "Who is doing what?"

Instead of searching through narrative blog posts, a user can query the ledger directly: "Show me all decisions related to 'Q3-budget'" or "List all open action items assigned to @franklin." The blog becomes a secondary artifact—a human-friendly view *of the ledger*, not the source of truth itself.

## 2. The Broken Assumption
This proposal challenges the core assumption that **Egregora's purpose is to create a narrative summary (a blog).**

> "We currently assume that the value is in the story of the conversation. This proposal asserts that the primary value is in the *outcomes* of the conversation—the decisions and actions—and the narrative is just context."

This shifts Egregora from a tool for reflection to a tool for accountability and execution. The blog is useful, but the Decision Ledger is indispensable.

## 3. The Mechanics (High Level)
*   **Input:** The same chat logs as the current system.
*   **Processing:** A new, primary "Decision Extraction Agent" runs *before* the `WriterAgent`. This agent's sole job is to scan the conversation and produce a structured list of `Decision` and `ActionItem` objects. These objects would contain the what, who, when, and a direct link back to the source messages.
*   **Output:** The primary output is `decisions.json` or a dedicated DuckDB table. The `WriterAgent` is then re-tasked to consume this structured data, using the conversation log as context to write a narrative *around* the key decisions, rather than trying to find the decisions within the narrative.

## 4. The Value Proposition
This solves the biggest problem in collaborative work: the gap between conversation and action. By making decisions and action items the central, first-class artifact of the system, Egregora becomes the de facto source of truth for a team's execution plan. It increases accountability, reduces ambiguity, and makes project management an emergent property of conversation, not a separate, manual process. This is a 10x leap in utility, transforming Egregora from a passive archivist into an active project manager.
