# 🏛️ The Symbiote Era (Sprint 3+)

**Status:** Active
**Epoch:** 2026-01-29 — Present
**Key Theme:** Modularity, Resilience, Observability
**Trigger Event:** The Great Refactor (Commit `059be01` by `janitor`)

---

## 🌅 Introduction: The Machine Wakes Up

The **Symbiote Era** marks the transition of Egregora from a set of monolithic "Batch Era" scripts into a reactive, modular, and resilient system. The name "Symbiote" reflects the architectural goal: the system should not just be a tool the user fires and forgets, but a partner that maintains its own state, handles errors gracefully, and provides deep observability into its processes.

This era was precipitated by the [Architecture Analysis of Jan 2026](../wiki/Architecture.md), which identified that the complexity of the original `write.py` (1400+ lines) had become a liability.

## 🏗️ Architectural Pillars

### 1. Modular Pipelines
The monolithic `write.py` has been decomposed into distinct logical domains:

- **ETL (`orchestration/pipelines/etl/`)**: Handles data ingestion, preparation (`preparation.py`), and privacy filtering. It is purely functional and side-effect free where possible.
- **Execution (`orchestration/pipelines/execution/`)**: The core processing logic (`processor.py`) that accepts prepared data and orchestrates agents.
- **Coordination (`orchestration/pipelines/coordination/`)**: Manages background tasks (`background_tasks.py`), state persistence, and inter-process communication.

The entry point `write.py` remains but has been reduced to a coordinator (~450 lines) that delegates work to these modules.

### 2. Explicit Configuration
Gone are the "magic numbers" buried deep in conditional logic. The Symbiote architecture enforces explicit configuration via `src/egregora/config/defaults.py`.
- **Single Source of Truth**: All default values (rate limits, window sizes, model names) are centralized in `PipelineDefaults`, `ModelDefaults`, etc.
- **Overridability**: Defaults can be cleanly overridden by runtime configuration without code changes.

### 3. Unified State
The system manages state through a unified **`PipelineContext`** (`src/egregora/orchestration/context.py`) which splits concerns into:
- **`PipelineConfig`**: Immutable configuration and paths.
- **`PipelineState`**: Mutable runtime state (clients, connections, caches, task stores).

This allows the system to pass a single context object that provides access to everything needed for execution, ensuring consistency.

### 4. Error Boundaries (Partial)
The "crash-on-first-error" pattern is being replaced. While a formal `ErrorBoundary` protocol is not yet fully implemented, the system now employs broad exception handling at the item processing level to prevent one bad window from crashing the entire pipeline.

## 🧩 Key Components

### The Orchestrator (`orchestration/`)
The brain of the system. It delegates:
- **`etl`**: Prepares the data.
- **`write.py`**: Loops through conversations and calls processing logic.
- **`journal.py`**: Records execution history to prevent re-processing.

### The Agents (`agents/`)
Specialized workers that perform discrete cognitive tasks.
- **Writer**: Converts chat windows into narrative posts.
- **Profile**: Updates author profiles based on new evidence.
- **Banner**: Generates visual assets for posts.

### The Sinks (`output_sinks/`)
Pluggable destinations for the generated content. Currently focused on MkDocs, but architected to support Notion, SQL, or other CMSs in the future.

## ⚠️ Known Technical Debt (Lore)

### The Ghost in the Shell (`write.py` vs `processor.py`)
Despite the creation of `src/egregora/orchestration/pipelines/execution/processor.py` to encapsulate item processing logic, the `write.py` coordinator currently defines its own local `process_item` function that duplicates much of this logic.
- **Impact**: Logic changes must be manually synced between the two files.
- **Status**: Identified for future refactoring.

## 📈 Evolution from Batch Era

| Feature | Batch Era (Sprint 1-2) | Symbiote Era (Sprint 3+) |
| :--- | :--- | :--- |
| **Structure** | Monolithic Scripts (`write.py`) | Modular Packages (`etl`, `execution`) |
| **Configuration** | Implicit / Magic Numbers | Explicit `defaults.py` |
| **Failure Mode** | Catastrophic Exit | Item-Level Isolation |
| **State** | Filesystem Artifacts | `PipelineContext` (In-Memory + Journal) |
| **Philosophy** | "Run this script" | "Manage this pipeline" |

## 🔮 Future Direction

The Symbiote Era lays the groundwork for:
- **Multi-Provider Support**: Seamlessly switching between Google Gemini, OpenAI, and Anthropic.
- **Dry-Run Mode**: Estimating costs and tokens before spending a dime.
- **Live Observability**: Real-time dashboards of pipeline progress.
- **Consolidation**: Removing the logic duplication in `write.py`.
