# RFC: The Egregora Knowledge Hub
**Status:** Moonshot Proposal
**Date:** 2025-12-25
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine a developer, new to a project, typing a natural language query into a simple search bar on a web interface: "What was the final decision on the Project Chimera caching strategy and why was it made?"

Instead of a list of blog post links, they receive a direct, synthesized answer:

> "The final decision for Project Chimera was to implement a write-through cache, invalidating on a 5-minute TTL. This was chosen over a write-back strategy because the team prioritized data consistency over raw performance, as documented in the 'Project Chimera Post-Mortem.' The key stakeholders were Alice, Bob, and Charlie. [Link to full post] [Link to conversation transcript]"

This isn't a website. This is a queryable, living knowledge base. The static blog is still there, but it's just one "view" into the Hub. Another developer could be using a VS Code extension to ask, "Show me all API schema decisions from the last quarter." A project manager could be looking at a Grafana dashboard, powered by the Hub's API, visualizing the communication frequency and decision velocity for their team.

The Egregora Knowledge Hub transforms the project's output from a static, passive archive into an active, dynamic intelligence service.

## 2. The Broken Assumption
> "We currently assume that **the ultimate purpose of Egregora is to generate a static website.** This forces all rich, multi-dimensional knowledge into a single, linear, one-size-fits-all format and prevents dynamic, user-driven exploration of the collective intelligence."

The static site is a dead end. It is a "read-only" artifact that cannot be interrogated. It freezes the knowledge in a specific presentation format. The true value lies not in the structured, interconnected data that underpins them. By making the website the final goal, we are throwing away the most valuable asset.

## 3. The Mechanics (High Level)
*   **Input:** The same chat logs and other knowledge sources. The ingestion pipeline remains largely the same.
*   **Processing:**
    *   **Service-Oriented Architecture:** Instead of a script that runs and exits, the core Egregora pipeline runs as a long-lived, persistent service (e.g., using FastAPI or a similar framework).
    *   **Persistent Knowledge Graph:** The data is not just written to files but loaded into a queryable state that represents documents, authors, topics, and decisions as nodes in a graph. DuckDB and LanceDB are still used, but they are treated as live databases for the service, not just as intermediate build artifacts.
    *   **Query Engine & API:** The service exposes a secure API (e.g., GraphQL or REST) that allows clients to query the knowledge graph. The API would have endpoints for:
        *   Natural language questions (powered by RAG).
        *   Structured queries for specific documents or metadata.
        *   Data for visualizations (e.g., social graphs, activity timelines).
*   **Output:** A JSON API is now the primary product. The static site generator becomes just one client of this API. Other clients could include:
    *   A dedicated, interactive web client for exploring the knowledge base.
    *   A Slack/Discord bot that queries the Hub.
    *   Integrations with BI tools like Grafana or Metabase.
    *   A programmatic client library for developers.

## 4. The Value Proposition
*   **From Archive to Utility:** The Hub transforms Egregora from a historical record into a daily-use utility for decision-making, onboarding, and research.
*   **Unlocks Personalized Knowledge:** Users are no longer limited to the pre-canned narrative of the blog. They can ask their own questions and get answers tailored to their specific context.
*   **Enables a Service Ecosystem:** By providing an API, Egregora becomes a platform. An entire ecosystem of tools and integrations can be built on top of the core knowledge base, multiplying its value.
*   **Future-Proofs the System:** The presentation layer is decoupled from the data layer. As new frontend technologies or visualization techniques emerge, they can be easily integrated as new "views" into the Hub without re-architecting the core system.
