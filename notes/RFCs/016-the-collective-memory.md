# RFC: The Collective Memory
**Status:** Moonshot Proposal
**Date:** 2024-07-26
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine Egregora is no longer a tool you *run*, but a service that's *always running*. It's a "fifth brain" for the group, a persistent, dynamic entity with a constantly evolving understanding of the conversations it's part of. Developers can query this "Collective Memory" via a simple API to build new, real-time experiences. A new team member could ask, "What's the history behind the 'Pure' project?" and get a coherent, synthesized answer with links to the key conversations. A bot could listen for the phrase "What do we think about..." and instantly surface the group's established position on the topic. The blog becomes just one possible *view* of the memory, not the final product.

## 2. The Broken Assumption
This proposal challenges the core assumption that Egregora is a **batch-processing tool**.
> "We currently assume that Egregora is a script that runs, processes a static file, and exits. This forces us into a reactive, historical mode and prevents us from building truly interactive, real-time applications on top of our data."

## 3. The Mechanics (High Level)
*   **Input:** Instead of a single file, Egregora ingests a continuous stream of messages from a message bus (like Kafka or Redis Streams). Adapters become long-running producers.
*   **Processing:** The core pipeline is replaced by a set of event-driven services. A "Modeling Service" continuously updates a knowledge graph or vector database in real-time. Instead of a monolithic "Writer Agent," we have smaller, specialized agents that react to changes in the model.
*   **Output:** The primary output is a stable, versioned, queryable API that exposes the "Collective Memory." The static site, RSS feeds, and other artifacts become consumers of this API, just like any other application.

## 4. The Value Proposition
This transforms Egregora from a niche static site generator into a **platform for building collaborative intelligence**. It unlocks an entire ecosystem of new tools: real-time bots, Q&A interfaces, semantic search, and proactive agents. We stop selling a retrospective blog and start providing a living, breathing knowledge asset for any group. It's the leap from archivist to oracle.
