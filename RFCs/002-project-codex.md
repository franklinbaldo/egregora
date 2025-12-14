# RFC: Project Codex (The Auto-Wiki)
**Status:** Moonshot Proposal
**Date:** 2025-05-28
**Disruption Level:** High (Structural Shift from Stream to State)

## 1. The Vision

Imagine you are a new member of an existing friend group. You feel lost. They keep referencing "The Noodle Incident of 2022" or arguing about "The Protocol."

Instead of asking "What does that mean?" and getting a vague answer, you go to the group's **Codex**.
You type "The Protocol" into the search bar.
A Wikipedia-style page appears.
*   **Definition:** The rules governing who chooses the movie on Friday nights.
*   **Origin:** Established Nov 12, 2021, by Dave.
*   **Controversies:** The "Rom-Com loophole" of 2023 (See: *Entry #405*).
*   **Related Entities:** *Dave*, *Friday Night*, *Bad Movies*.

The Codex isn't just a list of blog posts. It is a **living encyclopedia** of the group's shared reality. It stabilizes the ephemeral chaos of chat into permanent "Lore."

## 2. The Broken Assumption
> "We currently assume that a chat archive is a *Time Series* (chronological feed), but this prevents us from treating the group's history as a *Knowledge Base*."

Blogs (and chat logs) are linear. To understand a concept, you have to read the events in order.
Wikis are non-linear. They organize information by *Concept*.
Currently, Egregora extracts *Events* (Posts). It ignores the *State* (Facts). We are letting the most valuable asset—the group's "Canon"—slip through the cracks of the feed.

## 3. The Mechanics (High Level)

### Input
*   **Chat Logs:** The standard `Entry` stream.
*   **Existing Codex:** The current state of the Wiki (Markdown files).

### Processing
We move from a "Stateless Writer" to a "Stateful Gardener."

1.  **Entity Extraction (The Harvester):**
    *   As new chats come in, an LLM scans for Proper Nouns (People, Places) and recurring Abstract Concepts ("The Vibe," "The Bet").
    *   It uses Clustering (scikit-learn) on vector embeddings to detect when different terms refer to the same thing ("Dave's Car" = "The Rust Bucket").

2.  **The Wiki Gardener Agent:**
    *   This agent doesn't write posts; it *maintains pages*.
    *   **New Concept Detected:** It creates a stub page. `pages/concepts/the-noodle-incident.md`.
    *   **New Fact for Existing Concept:** It updates the page. "Update 2025: Dave sold The Rust Bucket."
    *   **Conflict Resolution:** If the chat contradicts the Wiki ("Wait, I thought the trip was in July?"), the Agent notes the dispute in a "Controversy" section on the page.

3.  **The Graph Topology:**
    *   We generate a semantic link graph.
    *   The UI isn't just a table of contents; it's a 3D force-directed graph (using D3.js or similar) showing how People connect to Events.

### Output
*   **Artifact:** A static Wiki site (MkDocs with `material/wiki` features enabled), separate from (but linked to) the Blog.
*   **Structure:** `/wiki/people/`, `/wiki/lore/`, `/wiki/events/`.
*   **UX:** Bi-directional linking. The Blog Post for "Friday Night" links to the Wiki Entry for "The Protocol." The Wiki Entry cites the original Blog Post as a source.

## 4. The Value Proposition
*   **Codification of Culture:** Communities are defined by their shared history. A Wiki *formalizes* that culture, making it feel "real" and momentous.
*   **Onboarding:** instant context for new members (or partners/spouses).
*   **Nostalgia 2.0:** Instead of "remember when we said X," it's "remember the *History of X*." It elevates banter to Legend.
*   **Utility:** "What was the recipe link Sarah shared 3 years ago?" The Wiki has a page for "Recipes" that aggregates them.
