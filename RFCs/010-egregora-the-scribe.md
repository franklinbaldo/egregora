# RFC: Egregora the Scribe
**Status:** Moonshot Proposal
**Date:** 2024-07-29
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine a project discussion in a busy chat. Ideas are flowing, consensus is building, and a key decision is made about the new database technology. In most chats, this decision is ephemeral, buried under dozens of subsequent messages within minutes. To find it later, someone has to scroll back, piece together the context, and manually add it to a wiki or project board.

With "Egregora the Scribe," the moment the team reaches a consensus, a new participant named "Egregora" interjects politely:

> **Egregora:** "It sounds like we've reached a decision. Can I confirm that we are moving forward with **Postgres** for the new database, citing **scalability** as the primary reason?
>
> `[👍 Confirm & Log]` `[👎 No, we're still discussing]`"

When a team member clicks "Confirm," the decision is instantly formalized, timestamped, and added to a dedicated, immutable decision log within the Egregora Knowledge Hub. The conversation continues, but now a critical piece of knowledge has been captured, verified, and stored *at the moment of its creation*. The Scribe doesn't just record history; it actively participates in writing it.

## 2. The Broken Assumption
This proposal shatters the assumption that **Egregora is a passive observer and the chat is a read-only artifact.**

> "We currently assume that the chat is a raw material that Egregora processes *after the fact*. This prevents us from capturing and formalizing knowledge when it's most valuable: in the moment it is created. The Scribe breaks the one-way data flow (`Chat -> Blog`) and introduces a real-time, interactive loop (`Chat <-> Egregora`)."

We are moving from a tool that documents decisions to a tool that *makes decisions official*.

## 3. The Mechanics (High Level)
*   **Input:** A real-time stream of chat messages from a new **Live Adapter** (e.g., for Slack, Discord, or Telegram).
*   **Processing:** A new stateful agent, "The Scribe," continuously analyzes the conversation to detect "decision signals."
    *   **Decision Detection:** A specialized language model trained to identify phrases of consensus, agreement, and resolution (e.g., "Okay, let's go with that," "We've all agreed," "So the plan is...").
    *   **Entity Extraction:** The model extracts the core components of the decision: the chosen option, the rejected alternatives, the stated rationale, and the key participants.
    *   **Confirmation Generation:** The Scribe composes a concise confirmation message, including interactive components (buttons, etc.) that the chat platform supports.
*   **Output:**
    *   **In-Chat Messages:** The Scribe posts messages and interactive prompts directly into the conversation, becoming a true participant.
    *   **The Decision Log:** Confirmed decisions are written as structured data (e.g., Atom entries) to the Content Library, forming a new, high-value artifact beyond the narrative blog post.

## 4. The Value Proposition
This transforms Egregora from a "nice-to-have" archival tool into a mission-critical system for **real-time governance and knowledge formalization.**

*   **Zero Knowledge Decay:** Decisions are captured with perfect fidelity at their source, eliminating the risk of them being lost, misremembered, or misinterpreted.
*   **Drastic Reduction in Manual Work:** The endless task of taking meeting notes and updating wikis is automated. The conversation *is* the documentation workflow.
*   **Creates an Action-Oriented Culture:** By prompting for confirmation, the Scribe encourages clarity and accountability, turning vague agreement into committed action.
*   **Unlocks a System of Record:** The decision log becomes a reliable, auditable source of truth for project history, which can be used for onboarding, reviews, and future RAG context.
