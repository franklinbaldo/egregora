# RFC: The Egregora Symbiote
**Status:** Moonshot Proposal
**Date:** 2024-07-26
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine a future where Egregora is not a historian you consult after the fact, but a real-time participant in your conversations. The Egregora Symbiote is an AI agent that lives within the chat, observing the flow of conversation and contributing at precisely the right moments to enhance the group's collective intelligence.

When a debate stalls, the Symbiote surfaces a relevant decision from six months ago. When a new team member asks a question, the Symbiote instantly provides a link to the canonical answer from the knowledge base. It doesn't just record history; it actively shapes better outcomes by connecting the past, present, and future of the conversation, in real-time. This transforms Egregora from a documentation tool into a true cognitive partner.

## 2. The Broken Assumption
This proposal challenges the most fundamental assumption of Egregora: that it is a **reactive, batch-processing system**.
> "We currently assume that Egregora operates on a historical corpus of text (a ZIP export) after the conversation has ended. This prevents us from influencing the quality and outcome of conversations *as they happen*."

By breaking this assumption, we move from passive archiving to active augmentation.

## 3. The Mechanics (High Level)
*   **Input:** Instead of a static file, the Symbiote would connect to a real-time message bus or streaming adapter for platforms like Slack, Discord, or even a local websocket for WhatsApp.
*   **Processing:** The core logic shifts from batch analysis to a low-latency, event-driven architecture. The Symbiote would maintain a continuously updated model of the conversation's context, using a combination of RAG on the historical archive and a short-term memory buffer for the current discussion. It would require an "intent detection" engine to know *when* and *how* to intervene.
*   **Output:** The Symbiote's output would be a new message posted directly into the chat, containing the relevant context, link, or summary.

## 4. The Value Proposition
The Egregora Symbiote represents a 100x increase in value. Instead of producing a slightly better historical record, it actively improves the quality of decisions and collaboration in real-time. It solves the "knowledge retrieval" problem at the exact moment the knowledge is needed, eliminating the friction of context switching and manual searching. It turns a passive archive into a living, breathing extension of the group's own memory.
