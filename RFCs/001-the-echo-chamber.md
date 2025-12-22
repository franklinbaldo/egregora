# RFC: The Echo Chamber (Synthetic Social Simulation)
**Status:** Moonshot Proposal
**Date:** 2024-05-22
**Disruption Level:** Total Paradigm Shift

## 1. The Vision

Imagine dropping a link to a breaking news article into the Egregora interface. Instantly, a chat window lights up.

*   **@Dave** makes a sarcastic joke about the headline.
*   **@Alice** replies with a crying-laughing emoji and a thoughtful counterpoint.
*   **@Bob** completely misses the point and goes on a tangent about crypto.

You are watching your group chat discuss something *they haven't actually discussed yet*.

This is **The Echo Chamber**.

Currently, Egregora is a "Time Capsule"—a way to preserve the past. The Echo Chamber transforms it into a "Crystal Ball"—a way to simulate the group's collective consciousness. It moves beyond **Archiving** (What did we say?) to **Modeling** (Who are we?).

Users can "summon" the Egregora to:
*   **Simulate reactions:** "How would the group react if I proposed a trip to Iceland?"
*   **Resolve disputes:** "Ask the Virtual Council who was right in the argument from 2018."
*   **Keep the memory alive:** Interact with the digital shadows of old friends or groups that have drifted apart.

## 2. The Broken Assumption

**The Constraint:** We currently assume that the value of the chat log lies in the **text itself** (the data).
**The Reality:** The value lies in the **personalities and relationships** (the model).

We treat the export as a static artifact to be indexed and searched. We assume `Output = Formatted Input`.
But LLMs allow us to treat the input as **training data**. The "Egregora" (the emergent group soul) is not the *history* of the chat; it is the *latent probabilistic distribution* of the group's interactions.

By limiting ourselves to RAG (retrieval), we are only looking backward. By embracing Simulation (generation), we unlock the future.

## 3. The Mechanics (High Level)

### Input: The Deep Profile
The current `ProfileWorker` is superficial. We need a **Persona Extraction Pipeline**:
1.  **Stylometric Analysis:** Vocabulary size, sentence structure, emoji usage, capitalization quirks.
2.  **Interaction Graph:** Who replies to whom? Who is the "main character"? Who is the "lurker"?
3.  **Belief Mapping:** Vector clusters of opinions held by specific users (e.g., "Alice loves sci-fi", "Bob hates politics").
4.  **Memory Injection:** A distinct RAG store for *each user*, allowing the simulated agent to recall "their" specific past experiences.

### Processing: The Simulation Engine
A new `Orchestrator` mode that runs a multi-agent loop:
*   **The Stage:** A shared context window representing the virtual chat room.
*   **The Actors:** Instances of LLMs (or a single model with swapped system prompts) playing the role of each user.
*   **The Director:** A meta-agent that manages turn-taking (deciding who speaks next based on the Interaction Graph probability) and injects external stimuli (news, questions).

### Output: Interactive Theater
*   **Web Interface:** A "Live Chat" view in the generated site (using WebAssembly or a lightweight backend) where users can watch the simulation unfold.
*   **"Ghost" Messages:** A special export format that looks like a real chat log but is tagged as `Synthetic`.

## 4. The Value Proposition

1.  **From Utility to Magic:** Static blogs are useful. A living simulation of your friends is *magical*. It maximizes the "Delight" factor.
2.  **True "Egregora":** It fulfills the product's namesake—creating an autonomous entity from the collective thoughts of the group.
3.  **Engagement Loop:** Users won't just visit the site to find an old recipe; they will visit to *play* with the group dynamics.
4.  **Viral Potential:** "Look what the AI thinks you would say about this" is incredibly shareable content within the group.

---
*The Architect will worry about the cost of multi-agent inference. The Sentinel will scream about identity theft. But the Visionary knows: this is the inevitable future of social archiving.*
