# RFC: 001 - The Egregora Symbiote
**Status:** Moonshot Proposal
**Date:** 2024-07-29
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine your group chat, but with a new member: an intelligent, helpful agent that isn't just a bot, but a true **symbiote**. This agent, the Egregora Symbiote, participates in the conversation in real-time. When a complex discussion concludes, it doesn't just wait for a manual export; it proactively says, "That was a great conversation. I've summarized the key decisions and action items. Here's the link to the permanent record." When someone asks, "What did we decide about the Q3 budget last month?" the Symbiote instantly retrieves and links to the answer from its knowledge base. It's not a tool you *run*; it's a collaborator you *talk to*. It transforms the group chat from a fleeting stream of consciousness into a self-organizing, perpetually accessible shared brain.

## 2. The Broken Assumption
This proposal challenges the most fundamental assumption of the current architecture: **that Egregora is a retrospective, batch-processing tool.**
> "We currently assume that Egregora operates *after the fact*, on historical data exports. This prevents us from delivering value *in the moment*, turning our product from a historian into an active participant."

By breaking this assumption, we evolve from a passive archivist into an active agent that enhances the conversation as it happens.

## 3. The Mechanics (High Level)
*   **Input:** Instead of a ZIP file, the input becomes a real-time stream of messages from a chat platform (via a new "Real-Time Adapter Framework").
*   **Processing:** The Symbiote maintains a persistent, in-memory model of the current conversation's context. It uses LLM function-calling to recognize conversational triggers (e.g., questions, decisions, task assignments) and interact with its long-term knowledge base (the existing DuckDB/LanceDB backend).
*   **Output:** The primary output is no longer a static blog post. It's a real-time message sent back into the chat, containing summaries, links, or answers. The static site becomes a secondary, browseable archive of the knowledge the Symbiote helps to create and organize.

## 4. The Value Proposition
This shift is transformative because it moves Egregora from a "nice-to-have" archival tool to an indispensable daily utility.
- **Instantaneous Value:** Knowledge is captured and retrieved in the moment it's needed, not days later.
- **Frictionless Interaction:** Users don't need to learn a new tool or visit a separate website. They interact with Egregora using the most natural interface: conversation.
- **Network Effects:** The more the group interacts with the Symbiote, the smarter and more valuable its knowledge base becomes, creating a powerful flywheel of adoption and utility.
