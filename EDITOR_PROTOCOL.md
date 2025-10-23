# Egregora Editor Protocol: Design and Implementation

This document outlines the design, implementation, and philosophy behind the minimal, line-based editing protocol recently added to Egregora.

## 1. The Plan: An LLM-First, Agentic Protocol

The primary goal was to create a dead-simple, LLM-first editing protocol that empowers an autonomous agent to refine documents. Instead of building a complex, human-centric editor with a rich feature set, we designed a minimal contract that an LLM agent can "speak" to safely modify a document.

The core principles behind the plan were:
- **Trust the LLM:** The agent, not the host, decides whether to make small, surgical edits or perform a full rewrite. The tools are simple and powerful, giving the agent the autonomy to choose the best strategy.
- **Simplicity Over Complexity:** We intentionally avoided complex synchronization models like Operational Transformation (OT) or CRDTs. A simple, atomic versioning system is sufficient to prevent race conditions in an agent-driven workflow.
- **Clean Separation of Concerns:** The protocol cleanly separates the **Editor** (which modifies documents) from the **Publisher** (which manages a queue). This implementation focused exclusively on the Editor.

## 2. How It Works

The protocol consists of a data model (`DocumentSnapshot`) and a set of tools (`Editor` class) that operate on it.

### The Document Snapshot

The agent receives a JSON object representing the current state of a document. This `DocumentSnapshot` is the source of truth for any editing session.

- **`doc_id`**: A unique identifier for the document.
- **`version`**: An integer that increments with every successful change. This is the cornerstone of our concurrency model.
- **`meta`**: A dictionary for metadata like title, authors, etc.
- **`lines`**: A dictionary mapping an integer index to the string content of each line. This line-based format allows for precise, targeted edits.

### The Editor Tools

An agent interacts with the document via three core tools:

1.  **`edit_line(expect_version, index, new)`**
    - **Purpose:** To replace a single line at a specific `index`.
    - **Concurrency:** The call will only succeed if `expect_version` matches the document's current `version`. On success, the version is incremented.

2.  **`full_rewrite(expect_version, content)`**
    - **Purpose:** To replace the entire content of the document. This is ideal for significant structural changes or heavy revisions.
    - **Concurrency:** This also uses `expect_version` for safe, atomic updates.

3.  **`finish(expect_version, decision, notes)`**
    - **Purpose:** To signal that the agent has completed its work on the document for now.
    - **`decision`**: Can be `"pass"` (ready for publishing) or `"hold"` (requires further review).
    - **Note:** The `finish` command currently simulates this action. A full publishing queue is planned for a future implementation.

### CLI Integration

For rapid prototyping and testing, these tools are exposed via the command line. The CLI implementation automatically persists any successful changes back to the source JSON file.

```bash
uv run egregora edit edit_line --expect_version 3 --index 2 --new "A newly rewritten line."
```

## 3. Design Decisions: The "Why"

- **Why Line-Indexed and Not a Single String?** A line-indexed format allows the LLM to make precise, surgical changes without needing to re-send the entire document for a small typo fix. It also maps cleanly to how text is often represented and processed.

- **Why Simple Versioning?** The `expect_version` check provides optimistic concurrency control. It's lightweight and solves the "stale edit" problem effectively without the immense overhead of more complex models like OT/CRDT, which are overkill for this use case.

- **Why a New `editor.py` Module?** We created a dedicated `editor.py` module to encapsulate all the logic for this new protocol. This keeps the editing functionality cleanly isolated from Egregora's core data processing pipeline, improving modularity and making the codebase easier to maintain.

## 4. What We Learned

- **Pydantic is a Great Contract Layer:** Using a Pydantic model for the `DocumentSnapshot` was highly effective. It provides runtime data validation and acts as a clear, enforceable schema for the data exchanged between the host and the agent.

- **CLI-First Prototyping is Fast:** Implementing a CLI wrapper around the new `Editor` class was a fast and effective way to test the core logic. It allowed us to interact with the protocol and verify its behavior before needing to build a full agent.

- **Minimalism Forces Clarity:** The constraint of having only three editor tools forced us to think clearly about the essential actions an agent needs. This resulted in a small, powerful, and highly focused API.
