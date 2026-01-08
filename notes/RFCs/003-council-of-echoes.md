# RFC: The Council of Echoes: From Archive to Advisor
**Status:** Moonshot Proposal
**Date:** 2025-05-20
**Disruption Level:** High (Paradigm Shift: From Passive to Active)

## 1. The Vision

The user opens Egregora not to read what happened, but to decide what will happen.

Instead of scrolling through a static archive of past conversations, they see a prompt: **"Summon the Council."**

They type a query: *"I'm thinking of quitting my job to start a goat farm. What does the group think?"*

Egregora doesn't just search for "goat farm." It spins up a real-time simulation. It hydrates the personalities of the group members—based on years of chat data, writing style, biases, and values—and places them in a virtual room.

*   **@TheRealist** (simulated) immediately asks about the financial viability.
*   **@TheJoker** (simulated) makes a pun about being the "GOAT."
*   **@TheSupporter** (simulated) offers encouragement but asks about logistics.

The user watches the debate unfold in real-time. They can intervene ("What if I have savings?"), steer the conversation, or just observe the collective wisdom of their social circle applied to a hypothetical future.

This is not a search engine. It is a **Social Digital Twin**. It turns the dead archives of the past into a living advisor for the future.

## 2. The Broken Assumption

> "We currently assume that the value of a chat archive is **historical**, but this prevents us from unlocking its **predictive** power."

Current Assumption:
*   The output is a "Blog" (static, linear, past-tense).
*   The primary interaction is "Reading" (high friction).
*   The data is "Dead" (immutable history).

New Paradigm:
*   The output is a "Simulation" (dynamic, branching, future-tense).
*   The primary interaction is "Consulting" (low friction).
*   The data is "DNA" (generative potential).

## 3. The Mechanics (High Level)

### Input: The "Soul" of the Group
We already have the raw materials in the Pure architecture:
*   **Profiles (DNA):** Author vectors, writing style samples, common phrases (already in `src/egregora/knowledge/profiles.py`).
*   **Knowledge (Memory):** The RAG store (`LanceDB`) containing the factual history and opinions of each member.
*   **Structure:** The Atom-centric data model.

### Processing: The Simulation Engine
We introduce a new Agent type: **The Echo**.
1.  **Hydration:** For a given query, the system retrieves the "Echoes" (Simulated Agents) of relevant group members.
2.  **Prompt Construction:** Each Echo is prompted with:
    *   **Persona:** "You are [User]. You speak like [Style]. You value [Values]."
    *   **Context:** Retrieved RAG chunks relevant to the topic (e.g., past opinions on careers/farming).
    *   **Goal:** "Debate the user's query with the other Echoes."
3.  **Orchestration:** A "Moderator" agent manages the turn-taking in a multi-agent loop, preventing hallucinations and keeping the debate focused.

### Output: The "Session"
*   **Interactive Interface:** A chat-like UI where the user interacts with the simulacra.
*   **Synthesized Report:** A summary of the "Council's Decision," highlighting consensus, conflict, and key advice.
*   **Audio Mode:** (Optional) Using TTS to let you "listen in" on the simulated meeting.

## 4. The Value Proposition

1.  **100x Engagement:** Reading old logs is boring. "Talking" to your friends (even when they aren't online) is addictive.
2.  **Asynchronous Wisdom:** Get the group's perspective immediately, without waiting for them to reply or waking them up.
3.  **Immortality:** Communities eventually die or drift apart. The Council preserves the *dynamic* of the group forever. It allows you to "revisit" the golden age of the group chat.
4.  **Privacy-First Social:** It uses your private data to build a private simulation. No data is leaked to a public model training set; it's local (or private-cloud) orchestration.

**Why this fits Egregora:**
Egregora means "Group Mind." V1/V2 built the *body* (the text). Pure builds the *brain* (vectors/RAG). The Council of Echoes wakes it up.
