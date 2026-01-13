# RFC: The Egregora API
**Status:** Moonshot Proposal
**Date:** 2026-01-15
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine Egregora not as a tool that generates a website, but as a headless platform that serves a live, queryable **Knowledge API**. The "Decision Ledger" is no longer a final artifact; it's a dynamic, real-time database accessible via GraphQL or REST endpoints. Developers can now build custom integrations, dashboards, and bots that consume the structured knowledge extracted from conversations.

A project manager could build a custom dashboard showing all open action items across all company chats. A developer could create a Slack bot that, when asked "@egregora what's the status of the Q3 budget?", queries the API and returns the latest decisions. The static blog becomes just one of many possible "clients" of the Egregora API, not the central product.

## 2. The Broken Assumption
This proposal challenges the most fundamental assumption of the project: **that Egregora is a self-contained, end-to-end tool.**

> "We currently assume that Egregora's job is to control the entire pipeline from chat log to final output (a blog). This proposal asserts that Egregora's primary job is to produce structured, machine-readable knowledge and make it programmatically available. The final output is someone else's problem."

This shifts Egregora from a product into a platform. It stops being a "chat-to-blog" converter and becomes the central nervous system for an organization's conversational knowledge.

## 3. The Mechanics (High Level)
*   **Input:** The same chat logs, but potentially ingested in real-time via webhooks or streaming adapters (building on the "Real-Time Adapter Framework" RFC).
*   **Processing:** The pipeline remains similar, with agents for enrichment and decision extraction. However, instead of writing to a local DuckDB file that powers a static site, the final step is to populate a persistent, production-grade database (e.g., PostgreSQL).
*   **Output:** A well-documented, public-facing API (likely GraphQL for its querying flexibility) that exposes the structured data—decisions, action items, key topics, and their relationships. Authentication would be handled via API keys.

## 4. The Value Proposition
This unlocks the full potential of the knowledge currently trapped within Egregora's internal database. It transforms the project from a niche tool into a foundational piece of infrastructure for any data-driven organization. It creates a developer ecosystem around Egregora, allowing for network effects and a proliferation of use cases we can't even imagine yet. This is the leap from a helpful utility to a critical, indispensable platform. It's the difference between selling a book and building a library.
