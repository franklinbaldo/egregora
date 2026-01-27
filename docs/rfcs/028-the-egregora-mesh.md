# RFC 028: The Egregora Mesh (Federated Knowledge)

**Title:** The Egregora Mesh
**Status:** Draft
**Type:** Moonshot 🔭
**Created:** 2026-01-26

## Problem Statement

**The Assumption:** Egregora is an isolated island.
Currently, an Egregora instance (and the knowledge within it) is trapped on a single machine or a single static site. If Team A uses Egregora for Engineering and Team B uses it for Sales, they cannot benefit from each other's context. Knowledge remains siloed, duplicating the fragmentation problems of the tools (Slack/WhatsApp) we are trying to fix.

## Proposed Solution

**The Vision:** Transform Egregora from an "Island" to a "Mesh Node".

The **Egregora Mesh** is a decentralized, peer-to-peer federation protocol that allows autonomous Egregora instances to securely share context, query each other's RAG stores, and cross-reference content.

This is not a central server. It is a web of trust.

### Key Components:

1.  **The Mesh Protocol:** A standardized API (over HTTP/AtomPub) for:
    *   **Discovery:** "Who are my trusted peers?"
    *   **Query:** "Do you have context on 'Project X'?"
    *   **Retrieval:** "Give me Entry ID `urn:uuid:...`."

2.  **Semantic Trust Contracts:**
    *   Instead of binary permissions (Public/Private), we define semantic boundaries: "Share technical architectural decisions with [Partner], but redact Author Names and financial data."
    *   The AI enforces these contracts during the retrieval process (Redaction-on-Read).

3.  **Federated RAG:**
    *   When a user asks a question, the local Agent can dispatch sub-queries to trusted peer nodes.
    *   "According to my logs AND the Engineering Team's logs..."

## Value Proposition

*   **Break Down Silos:** Connect disparate teams without forcing them into a single monolithic tool.
*   **Scale Context:** Knowledge grows quadratically with the number of connected nodes.
*   **Preserve Privacy:** Data stays local/private by default; sharing is explicit and granular.
*   **Resilience:** No central point of failure.

## BDD Acceptance Criteria

```gherkin
Feature: Federated Context Query
  As a User of Egregora Node A (Sales)
  I want to ask a question that requires context from Node B (Engineering)
  So that I can answer customer questions about technical timelines accurately

  Scenario: Successful Federated Query
    Given Node A trusts Node B with "Read Access" to "Technical Tags"
    And Node B contains a post about "Feature X Delay" tagged "Technical"
    When I ask Node A "When is Feature X coming?"
    Then Node A should dispatch a query to Node B
    And Node B should return the relevant context (redacting sensitive internal comments)
    And Node A should synthesize an answer citing Node B as the source

  Scenario: Blocked Query (Privacy Boundary)
    Given Node A trusts Node B with "Read Access" to "Public Tags" only
    And Node B contains a post about "Secret Project Y" tagged "Internal"
    When I ask Node A "Tell me about Secret Project Y"
    Then Node B should return "No accessible context found"
    And Node A should answer based only on local data

  Scenario: Cross-Site Reference Resolution
    Given a post in Node A links to `atom://node-b.com/entry/123`
    When I view the post in Node A
    Then the link should expand into a summary card of the content from Node B
    And the summary should strictly respect the privacy visibility of the viewer
```

## Implementation Hints

*   **Identity:** Use DID (Decentralized Identifiers) or public/private key pairs for Node identity.
*   **Transport:** ActivityPub or a simplified AtomPub extension.
*   **Authorization:** OAuth 2.0 or a capability-based token system.
*   **Discovery:** A simple `.well-known/egregora-peers.json` file to bootstrap trust.

## Risks

*   **Complexity:** Distributed systems are hard. Synchronization, timeouts, and consistency.
*   **Security:** Expanding the attack surface. A compromised node could try to scrape data from peers.
*   **Performance:** RAG is slow; Federated RAG is slower. Latency management is critical.
