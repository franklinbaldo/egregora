# 🏛️ Architecture: The Batch Era

**Status:** Historical (Sprint 1-2)
**Next Epoch:** [The Symbiote Era](Architecture-Symbiote-Era.md)

## Overview
The **Batch Era** describes the architectural state of the system where **Egregora** operates as a discrete, scheduled command-line interface (CLI) tool. In this era, the system wakes up, performs a batch of work, and shuts down. It has no persistent memory in RAM; all state is persisted to disk (databases, markdown files) between runs.

## 🏗️ The Core Paradigm: Batch Processing

At its heart, Egregora is a **Batch Processing Engine**. It ingests a stream of data (chat logs, documents), slices it into time-based "Windows," and processes each window independently to generate artifacts (Blog Posts, Profile Updates, Journals).

### Key Concepts

1.  **The Window**: A transient view of conversation data. While historically temporal (e.g., "Monday 10:00 AM - 12:00 PM"), modern "Phase 6" windowing supports **Byte-based Packing** to maximize context usage (~4 bytes/token) irrespective of time boundaries.
2.  **The Pipeline**: The linear sequence of steps applied to a window: `Ingest -> Window -> Enrich -> Write -> Persist`.
3.  **Idempotency**: The system is designed to be resumable. Completed windows are recorded as `DocumentType.JOURNAL` entries in the database. Subsequent runs query these entries to skip already-processed data.

## ⚙️ The Engine: `PipelineRunner`

The `PipelineRunner` (`src/egregora/orchestration/runner.py`) is the central orchestrator. It manages the lifecycle of the batch process.

### Recursive Splitting Mechanism

One of the most critical features of the Runner is its ability to handle **Prompt Size Limits**.
- **Problem**: A 2-hour window might contain more tokens than the LLM can handle.
- **Solution**: The Runner detects `PromptTooLargeError` and recursively splits the window into smaller sub-windows (e.g., two 1-hour windows), re-processing them until they fit.
- **Implementation**: This is handled via a queue-based loop in `_process_window_with_auto_split`.

### Journal-Based State

The Runner uses a "Journal" mechanism for state tracking, persisted as `DocumentType.JOURNAL`.
- Before processing a window, it checks if a Journal entry exists for that specific signature (hash of data + logic + model).
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
Located in `src/egregora/output_sinks/`.
The abstraction layer for where artifacts go (File System, S3, Database). Currently, it primarily targets the local file system (`mkdocs` structure).

## Historical Significance
This architecture was essential for bootstrapping the system. It allowed for:
- **Simplicity:** No complex async servers or event loops (initially).
- **Stability:** "Crash-only software" principles applies; if it fails, just run it again.
- **Lazy Context Loading:** As documented in [The Lazy Historian](../personas/lore/blog/002-the-lazy-historian.md), the system optimizes for cache hits by lazily loading RAG and Profile data based on the assumption that the world is static during execution.

## The Coming Shift
As of Sprint 2, the **Visionary** and **Simplifier** steered the system toward the **Symbiote Era**: a real-time, event-driven architecture that lives alongside the user. This required dismantling the "Batch" assumptions, particularly the static context loading.
