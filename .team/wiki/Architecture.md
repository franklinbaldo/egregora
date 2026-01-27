# Architecture & Core

> **Status:** Active (Sprint 1)
> **Paradigm:** Batch Processing / Windowed Execution

This document outlines the core architecture of the **Egregora** system as of Sprint 1.

## 🏗️ The Core Paradigm: Batch Processing

At its heart, Egregora is a **Batch Processing Engine**. It ingests a stream of data (chat logs, documents), slices it into time-based "Windows," and processes each window independently to generate artifacts (Blog Posts, Profile Updates, Journals).

### Key Concepts

<<<<<<< HEAD
1.  **The Window**: A transient view of conversation data. While historically temporal (e.g., "Monday 10:00 AM - 12:00 PM"), modern "Phase 6" windowing supports **Byte-based Packing** to maximize context usage (~4 bytes/token) irrespective of time boundaries.
2.  **The Pipeline**: The linear sequence of steps applied to a window: `Ingest -> Window -> Enrich -> Write -> Persist`.
3.  **Idempotency**: The system is designed to be resumable. Completed windows are recorded as `DocumentType.JOURNAL` entries in the database. Subsequent runs query these entries to skip already-processed data.
=======
1.  **The Window**: A temporal slice of conversation history (e.g., "Monday 10:00 AM - 12:00 PM"). The system operates on one window at a time.
2.  **The Pipeline**: The linear sequence of steps applied to a window: `Ingest -> Window -> Enrich -> Write -> Persist`.
3.  **Idempotency**: The system is designed to be resumable. If a window is processed, it is recorded in the `JOURNAL`, and subsequent runs will skip it.
>>>>>>> origin/pr/2742

## ⚙️ The Engine: `PipelineRunner`

The `PipelineRunner` (`src/egregora/orchestration/runner.py`) is the central orchestrator. It manages the lifecycle of the batch process.

### Recursive Splitting Mechanism

One of the most critical features of the Runner is its ability to handle **Prompt Size Limits**.
- **Problem**: A 2-hour window might contain more tokens than the LLM can handle.
- **Solution**: The Runner detects `PromptTooLargeError` and recursively splits the window into smaller sub-windows (e.g., two 1-hour windows), re-processing them until they fit.
- **Implementation**: This is handled via a queue-based loop in `_process_window_with_auto_split`.

### Journal-Based State

<<<<<<< HEAD
The Runner uses a "Journal" mechanism for state tracking, persisted as `DocumentType.JOURNAL`.
- Before processing a window, it checks if a Journal entry exists for that specific signature (hash of data + logic + model).
=======
The Runner uses a "Journal" mechanism for state tracking.
- Before processing a window, it checks if a Journal entry exists for that specific time range and signature.
>>>>>>> origin/pr/2742
- If found, it skips the window (`⏭️ Skipping window...`).
- This allows the pipeline to be interrupted and restarted without duplicating work.

## 🧩 Core Components

### 1. The Enricher
Located in `src/egregora/agents/enricher.py`.
Responsible for augmenting raw text with metadata, summaries, and entity extraction *before* the Writer sees it.

### 2. The Writer
Located in `src/egregora/agents/writer.py`.
The "Creative" engine. It takes the enriched window and generates the Markdown content for the blog post.

### 3. The Output Sink
Located in `src/egregora/output_adapters/`.
The abstraction layer for where artifacts go (File System, S3, Database). Currently, it primarily targets the local file system (`mkdocs` structure).

---

<<<<<<< HEAD
## 🔮 Future Architecture: The Symbiote

*Status: In Planning (Sprint 2/3)*

The **Visionary** has proposed a paradigm shift from the current "Passive Archivist" (Batch Processing) to an "Active Collaborator" model known as the **Egregora Symbiote**.

### Key Shifts
- **Batch -> Real-time:** Moving from "Windows" to continuous event streams.
- **Unstructured -> Structured:** Implementing a **Structured Data Sidecar** to extract knowledge graphs from conversations in near real-time.
- **Read-Only -> Interactive:** Allowing the system to participate in conversations rather than just observing them.

*For more details, see [Sprint 2 Plans](../sprints/sprint-2/visionary-plan.md) and the [Glossary](Glossary.md).*
=======
*Archivist Note: This architecture is currently under review by the **Visionary** for a potential shift towards a "Symbiote" model (Real-time + Structured Sidecar). See [Sprint 2 Plans](../sprints/sprint-2/visionary-plan.md).*
>>>>>>> origin/pr/2742
