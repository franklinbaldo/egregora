# RFC: Egregora Symbiote
**Status:** Moonshot Proposal
**Date:** 2025-12-24
**Disruption Level:** Total Paradigm Shift

## 1. The Vision

Imagine your group chat. A complex technical problem is being discussed. Arguments are circular. Key information from three weeks ago is lost in the scrollback. Suddenly, a new participant, **`egregora-bot`**, posts a message:

> **`egregora-bot`**: "Pausing the discussion for a moment. I've synthesized the key points and found a relevant decision from our previous project (`#project-phoenix-archive`).
>
> **Summary of Current Debate:**
> - **Alice's Position:** We should use microservices for scalability. (Pros: isolation, independent deploys. Cons: complexity).
> - **Bob's Position:** A monolith is faster to build. (Pros: simplicity, speed. Cons: long-term maintenance).
>
> **Relevant External Context (from the blog):**
> - In the "Project Phoenix Post-Mortem," we concluded that our biggest bottleneck was not scalability, but developer onboarding. The monolithic architecture was cited as a major win for getting new hires productive quickly. [Link to Post]
>
> **Recommendation:**
> Has the team's priority shifted from "speed of onboarding" to "long-term scalability"? If not, the previous conclusion suggests Bob's approach aligns better with our established goals.

The team stops. The context is surfaced. The decision is made in minutes, not hours. The bot has not just archived the past; it has injected it into the present. Egregora is no longer a passive historian; it's an active, symbiotic participant in the creation of knowledge.

## 2. The Broken Assumption

> "We currently assume that **Egregora is a read-only system**. It consumes chat logs and produces a static, external artifact (a blog). This prevents us from **closing the loop and delivering value back into the conversational context where it is most needed.**"

The current model treats the blog as the final product. This proposal reframes the blog as an intermediate knowledge base. The *real* product is a higher-quality conversation, and the highest-leverage place to deliver that value is back in the chat itself.

## 3. The Mechanics (High Level)

*   **Input:**
    *   **Real-time Chat Stream:** Instead of a one-time batch export, Egregora needs a live connection to the chat platform (via webhook or a bot user).
    *   **Triggers:** The bot would listen for specific triggers:
        *   **Keywords:** `@egregora summarize`, `@egregora find decision`
        *   **Heuristics:** Detects a "stuck" conversation (e.g., high message velocity, low semantic drift, repeated keywords).
        *   **Scheduled Digests:** A daily "what you missed" post.

*   **Processing:**
    *   **Real-time RAG:** The live message stream is continuously embedded and compared against the LanceDB vector store (the blog's knowledge base).
    *   **Agentic Core:** A new "Symbiote Agent" would be responsible for:
        1.  **Intent Recognition:** Is this a question? A summary request? A stuck conversation?
        2.  **Context Retrieval:** Query the knowledge base for relevant posts, decisions, and summaries.
        3.  **Response Generation:** Synthesize the retrieved context into a concise, actionable message.
        4.  **Action Execution:** Post the message back to the chat.

*   **Output:**
    *   **In-Chat Messages:** Formatted Markdown messages posted by the `egregora-bot` user.
    *   **Interactive Components:** (Future) Buttons or interactive elements in the chat to refine the bot's search or confirm a decision.
    *   **Implicit Blog Updates:** The bot's own posts become part of the chat log, which are then processed by the existing pipeline, creating a self-reinforcing knowledge loop.

## 4. The Value Proposition

*   **From Passive Archive to Active Intelligence:** Egregora transforms from a "nice-to-have" historical record into an "indispensable" real-time cognitive partner. It's the difference between a library and a librarian.
*   **Reduces Knowledge Latency:** Instead of forcing users to leave the conversation, search the blog, and bring context back, the context is delivered proactively, exactly when and where it's needed. This collapses the OODA loop (Observe, Orient, Decide, Act) of group decision-making.
*   **Creates a Flywheel Effect:** The bot's interventions improve the quality of the conversation. The improved conversation leads to better, more structured blog posts. The better blog posts provide higher-quality context for the bot's future interventions. This is a virtuous cycle.
*   **Unlocks the Adjacent Possible:** This opens the door to entirely new features: proactive meeting agendas, automated decision logs, and even using the chat as a command line to orchestrate external systems.
