# RFC: The Egregora Symbiote
**Status:** Moonshot Proposal
**Date:** 2024-07-29
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine Egregora is no longer a historian, but a member of the team. It lives inside the chat, listening in real-time. When a discussion spirals, it interjects: "This sounds like the 'Project Phoenix' debate from last month. Here's the decision doc." When a new team member asks a question, the Symbiote instantly provides the canonical answer with links to the blog. It doesn't just record history; it shapes it. It helps the group build a shared brain, surfacing institutional knowledge at the moment it's most needed. The blog becomes a side effect, an artifact of a much deeper, continuous synthesis of knowledge that happens *during* the conversation, not after.

## 2. The Broken Assumption
This proposal challenges the core assumption that Egregora is a **batch-processing, post-facto archival tool**.
> "We currently assume that Egregora's job is to analyze conversations *after* they happen, but this prevents us from influencing the *quality* of those conversations in real-time and stops knowledge from being immediately reusable."

## 3. The Mechanics (High Level)
*   **Input:** A real-time stream of messages from chat platforms (e.g., via webhooks, APIs).
*   **Processing:** An always-on "Symbiote" agent that maintains a dynamic in-memory state of the current conversation. It uses the existing RAG knowledge base not for writing blog posts, but for identifying relevant context to inject back into the conversation. It can classify message intent (question, decision, task) and trigger actions.
*   **Output:** Messages posted directly into the chat, either proactively (e.g., "I've noticed you're discussing planning. Here's the Q3 roadmap.") or reactively (e.g., in response to `@egregora, what was our decision on the logo?`).

## 4. The Value Proposition
This transforms Egregora from a useful utility into an indispensable team member. It solves the "knowledge retrieval" problem by eliminating the need to search. It makes the group smarter, more consistent, and more efficient by leveraging its own history as an active, queryable resource. It's the leap from a static knowledge base to a dynamic, collective intelligence.
