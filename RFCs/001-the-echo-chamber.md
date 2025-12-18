# RFC: The Echo Chamber (Interactive RAG Simulation)

**Status:** Moonshot Proposal
**Date:** 2025-05-18
**Disruption Level:** Total Paradigm Shift (From Static Archive to Living Simulation)

## 1. The Vision

The "blog" is dead. The "archive" is a tomb. The future of Egregora is **"The Echo Chamber."**

Imagine a reader navigating to an "episode" (formerly a blog post) about a specific event. Instead of reading a static transcript, they enter a **Simulated Chatroom**.

The original participants are present, but they are **AI Personas** (Digital Twins) trained on the specific psychometrics, linguistic patterns, and knowledge base of the real group members *at that point in time*.

The reader can:
*   **Lurk:** Watch the conversation replay as if it were live.
*   **Interject:** Type a message into the chat. The AI Personas *react* to the intrusion.
    *   *Alice (AI)* might get defensive about her opinion on the movie.
    *   *Bob (AI)* might make a joke about the reader's username.
*   **Query the Hive:** Ask "Why did you guys decide this?" and get a consensus answer synthesized from the group's collective memory.

This isn't reading history; it's **time travel**. It turns the passive consumption of a "log" into an active, social experience. It transforms Egregora from a "Static Site Generator" into a **"Social Simulation Engine."**

## 2. The Broken Assumption

We currently operate under two limiting assumptions:

1.  **"The Chat is Over":** We assume that once the export happens, the conversation is finished and can only be observed. This ignores the potential for *counterfactual history* and *ongoing engagement*.
2.  **"The Output is a Document":** We assume the final artifact must be HTML text. This ignores the native modality of the source material: *Conversation*.

By breaking these, we move from **Archival (Read-Only)** to **Resurrection (Read-Write)**.

## 3. The Mechanics (High Level)

### Input
*   **Raw Chat Logs:** (Existing) used for "Ground Truth".
*   **Psychometric Profiling:** (New) The `ProfileWorker` is upgraded to generate not just bios, but "System Prompts" for each user.
    *   *Tone:* Sarcastic, verbose, emoji-heavy?
    *   *Relationships:* Who does Alice usually agree with? Who does she fight with?
    *   *Beliefs:* What are their core stances on repeated topics?

### Processing (The "Holodeck" Engine)
*   **Vectorized Memory:** Each persona has access to their *own* past messages (RAG) to ensure consistency.
*   **Orchestrator Agent:** A "Dungeon Master" AI that manages the simulation flow, decides which Persona speaks next, and injects the Reader's input into the context.
*   **WebAssembly Client:** The simulation logic (or a lightweight version) runs *in the browser* via WebAssembly + LLM API calls, keeping the "site" static but the "experience" dynamic.

### Output
*   **The "Echo" Interface:** A UI that looks exactly like a WhatsApp web client.
*   **Dynamic Transcripts:** A session log that records the *new* timeline created by the reader's interaction.

## 4. The Value Proposition

*   **10x Engagement:** Readers spend seconds scanning a blog post. They will spend *hours* playing with a simulator.
*   **True Immersion:** It captures the *vibe* of a community, not just the facts.
*   **The "Digital Twin" Utility:** For the group members themselves, it becomes a tool for reflection ("Would I really say that?"), conflict resolution ("Let's simulate how this argument would go"), and immortality ("Our friendship lives on in the code").
