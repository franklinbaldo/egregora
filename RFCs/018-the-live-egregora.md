# RFC: The Live Egregora
**Status:** Moonshot Proposal
**Date:** 2024-08-01
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine a heated debate in a project's WhatsApp group. The team is going in circles, re-litigating a decision made three weeks ago. Suddenly, a new participant, **Egregora**, interjects:

> "Hold on. On May 12th, we decided against this approach because of the database scaling issue. [link to the blog post summary]. The key blocker was @-jane's point about AWS costs. Has that changed?"

The conversation stops. The team course-corrects instantly. Later that day, Egregora proactively summarizes a long technical discussion, assigns action items based on the conversation, and saves the summary to the knowledge base without anyone needing to run a command. Egregora is no longer a tool you run; it's a team member you collaborate with.

## 2. The Broken Assumption
This proposal challenges the most fundamental assumption of the Egregora V2 and the proposed V3 architecture:

> "We currently assume that **Egregora is a retrospective, batch-processing tool** that analyzes historical chat logs. This prevents us from **delivering value to the user in the moment of collaboration.**"

The current model forces users to switch context—from the active conversation to the static knowledge base—to get value. The "Live Egregora" vision inverts this, bringing the knowledge directly into the conversation, right when it's needed.

## 3. The Mechanics (High Level)
*   **Input:** Instead of a static `_chat.txt` file, the input becomes a real-time stream of messages from a live source (e.g., a WhatsApp Web adapter, a Slack bot, a Discord bot).
*   **Processing:** The core architecture shifts from a batch pipeline (`Stream[Entry] -> Stream[Entry]`) to an event-driven, stateful agent. It processes one message at a time, maintains the context of the current conversation, and decides when to act.
*   **Output:** The primary output is no longer a generated static site. It's a message sent back to the live chat. The static site becomes a secondary, derivative artifact—an archive of the agent's interactions and summaries.

## 4. The Value Proposition
This is not an incremental improvement; it is a transformation of the product's core identity.
- It moves Egregora from a passive, "nice-to-have" tool for historical analysis into an active, **indispensable team member** that improves the quality and velocity of work *as it happens*.
- It solves the "dead knowledge" problem permanently. The knowledge base is no longer a place you have to remember to go; it's an active participant in your conversations.
- It unlocks a whole new class of features: on-demand summaries, duplicate conversation detection, real-time decision tracking, and proactive context injection.
