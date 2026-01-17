# RFC: The Egregora Mesh
**Status:** Moonshot Proposal
**Date:** 2026-01-17
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine a world where your "Engineering" Egregora can ask your "Product" Egregora: "What was the decision on the new login flow?" without having access to the raw Product chat logs. Or where a consultancy's Egregora can query a client's Egregora for "key stakeholders" before a meeting.

The **Egregora Mesh** transforms isolated knowledge silos into a federated intelligence network. It introduces the **Inter-Egregora Protocol (IEP)**, allowing distinct Egregora instances to securely expose specific knowledge sub-graphs (Decisions, Entities, Summaries) to other trusted instances, creating a "Collective Consciousness" across an organization or ecosystem.

## 2. The Broken Assumption
This proposal flips the assumption that **Egregora is an island.**

> "We currently assume that an Egregora instance is a solitary observer of a single chat history, and its knowledge begins and ends with that chat. This proposal asserts that Egregora is a node in a network, and its true value is realized when it connects to other nodes."

## 3. The Mechanics (High Level)
*   **The Protocol:** A standardized JSON-over-HTTP protocol (IEP) for querying knowledge entities.
*   **The Artifact:** A standardized "Portable Knowledge Artifact" (PKA) format (see RFC 025) serves as the data interchange model.
*   **The Trust Model:** A "Circle of Trust" configuration where instances exchange public keys to authorize specific query types (e.g., "Allow access to public decisions, deny access to raw quotes").
*   **The Query:** Federated Search. "Search for 'Auth' across all connected nodes."

## 4. The Value Proposition
This solves the "Fragmented Knowledge" problem in large organizations. Engineering talks on Slack/WhatsApp A, Product on B, Sales on C. Currently, these are three separate black boxes. The Mesh connects them. It allows for cross-pollination of ideas ("Sales is complaining about X, which Engineering just fixed in Y") without compromising the privacy of the raw conversations. It turns Egregora from a "Team Tool" into "Organizational Infrastructure."
