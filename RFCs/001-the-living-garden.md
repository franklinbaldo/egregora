# RFC: The Living Garden (Dynamic Knowledge Synthesis)
**Status:** Moonshot Proposal
**Date:** 2024-05-23
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine Egregora not as a historian that writes a report and files it away forever, but as a **Gardener**.

When you open the site, you don't just see "This Week's Updates." You see that the "Philosophy" section has expanded because the group discussed ethics last Tuesday. You see that the "2021 Predictions" page has been updated with a "Retrospective" sidebar because an event in 2024 confirmed a theory.

The content is **alive**. Old posts are not static artifacts; they are living documents that the AI actively maintains, links, refactors, and updates. The system doesn't just *add* to the pile; it *composts* the noise and *cultivates* the signal.

The user experience shifts from "Reading a Log" to "Exploring a Mind."

## 2. The Broken Assumption
**Assumption:** *The arrow of time is linear and immutable.* (Once a post is written, it is done. New data only creates new posts).

**Why this breaks us:**
1.  **Stagnation:** Old content rots. Insights from 2020 are lost because they aren't linked to related insights from 2024.
2.  **Fragmentation:** We have 50 separate posts mentioning "Pizza," but no single authoritative source on the group's "Pizza Theory."
3.  **Low Signal:** The user has to manually synthesize connections between disparate events.

## 3. The Mechanics (High Level)
*   **Input:** The same stream of `Entry` objects (Chat Logs), plus the *existing* corpus of `Documents` (The Site).
*   **Processing (The Gardener Agent):**
    *   **The Synthesizer:** A background process that wakes up when the system is idle. It clusters new topics with old topics.
    *   **The Refactorer:** If it detects high overlap (e.g., "We talked about Aliens again"), it doesn't just write a new post. It *edits* the "Aliens" Semantic Page, adding the new conversation as a new chapter and updating the summary.
    *   **The Linker:** It traverses old posts and inserts "Forward Links" (e.g., "Update 2024: This actually happened!").
*   **Output:** A **Wiki-First** architecture (Obsidian-style) rather than a Blog-First architecture.
    *   *Nodes:* Concepts/Topics.
    *   *Edges:* Conversations/Events.

## 4. The Value Proposition
*   **10x Utility:** The site becomes a reference book, not a diary. You go there to find answers, not just to reminisce.
*   **Compounding Value:** The more you chat, the *better* the old content gets. Currently, more chat just means more noise to wade through.
*   **True Egregore:** It actually models the collective intelligence, which evolves and changes its mind, rather than just recording a stream of consciousness.
