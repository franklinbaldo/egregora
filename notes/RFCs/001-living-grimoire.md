# RFC: The Living Grimoire (Project Alexandria)
**Status:** Moonshot Proposal (Prototyped)
**Date:** 2025-05-15
**Disruption Level:** High (Paradigm Shift from Temporal to Conceptual)

## 1. The Vision
Imagine you are a member of a long-running group chat (5+ years). You don't want to "read the blog" of what you said 3 years ago on a Tuesday. You want to know: * "What is our canon?" * "Who is 'Gary'?" * "What was 'The Great Noodle Incident'?"

In this vision, Egregora doesn't just output a feed of posts; it maintains a **Living Wiki**.
*   You visit the site and see a "Concepts" or "Lore" tab.
*   You click on "Gary" (a friend who left the group in 2021). You see a generated biography: *"Gary was a chaotic neutral member known for [X] and [Y]. He was last seen in the logs on [Date]."*
*   You search for "Camping Trip". You get a synthesized article combining the 2018, 2019, and 2022 trips into a coherent narrative history, with cross-links to "The Bear Attack" and "Lost Tents".

The site is no longer just an archive; it is the **Encyclopedia of Us**. It feels like browsing a dedicated Fandom Wiki for your own life, auto-written by a super-intelligent historian.

## 2. The Broken Assumption
**"The primary unit of human conversation is the Event (Time)."**

Current Architecture (V3) is "Atom-Centric." It assumes that `Entry` (a point in time) is the atomic unit of truth.
*   *Limitation:* Human memory is semantic, not episodic. We remember "Concepts" and "Relationships," not "Timestamps."
*   *Friction:* To understand a running joke, a user currently has to search for keywords and manually piece together 50 disparate blog posts.

We assume that preserving the *sequence* is the goal. But the goal is preserving the *meaning*.

## 3. The Mechanics (High Level)

### A. Input: The "Atom" Stream
We still ingest `Entry` objects (the temporal stream). This remains the "Raw Ore."

### B. Processing: The "Concept Miner" (New Engine)
We introduce a parallel processing layer that sits *above* the Writer Agent.
1.  **Entity Extraction:** As entries flow in, the system identifies recurrent Named Entities (People, Places, "Canon Events").
2.  **Concept Clustering:** It groups disparate entries that discuss the same entity, even if separated by years.
3.  **Synthesis Agent:** An LLM ("The Historian") reads the cluster of 50+ mentions of "The Noodle Incident" and writes a *single, definitive Wiki Page*.
4.  **Graph Linkage:** It identifies relationships (e.g., "Gary" -> *participated_in* -> "The Noodle Incident") and builds a navigation graph.

### C. Output: The "Grimoire" Artifact
*   **Format:** A set of interlinked Markdown documents (Wiki style).
*   **Update Cycle:** Continuous. When a new chat mentions "The Noodle Incident," the Historian re-reads the Wiki Page and *updates* it with the new context ("Update 2025: The incident was referenced again in context of...").

## 4. The Value Proposition
1.  **10x Utility:** Transforms "Data Junk" (thousands of old messages) into "Structured Lore."
2.  **Engagement:** Browsing a Wiki of your friends is infinitely more addictive than scrolling a timeline. It creates a sense of "Legacy."
3.  **The "Sticky" Factor:** This moves Egregora from a "Tool" (that you run once a month) to a "Platform" (that you curate and explore).
4.  **AI Alignment:** This leverages what LLMs are best at (Synthesis and Summarization) rather than just Formatting.

## 5. Technical Prototype Findings (2025-05-15)
A prototype script (`scripts/prototype_grimoire.py`) successfully demonstrated the pipeline:
1.  **Extraction:** Pydantic-AI agents can reliably extract `Concept` objects (Name, Type, Description) from chat logs.
2.  **Data Model:** A `WikiPage` model (extending `Document`) was created to store structured metadata (aliases, relations) alongside the markdown content.
3.  **Synthesis:** The "Historian" agent can aggregate multiple extractions into a single coherent narrative.

**Next Steps:**
*   Implement `ConceptStore` (likely using LanceDB or DuckDB) to persist extractions and support incremental updates.
*   Integrate the "Extraction" phase into the main ingestion pipeline.
*   Build a dedicated "Wiki Builder" worker that runs periodically.
