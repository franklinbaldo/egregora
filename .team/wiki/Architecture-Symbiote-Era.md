# 🏛️ The Symbiote Era (Sprint 3+)

**Status:** Active
**Epoch:** 2026-01-26 — Present
**Key Theme:** Modularity, Resilience, Observability

---

## 🌅 Introduction: The Machine Wakes Up

The **Symbiote Era** marks the transition of Egregora from a set of monolithic "Batch Era" scripts into a reactive, modular, and resilient system. The name "Symbiote" reflects the architectural goal: the system should not just be a tool the user fires and forgets, but a partner that maintains its own state, handles errors gracefully, and provides deep observability into its processes.

This era was precipitated by the [Architecture Analysis of Jan 2026](../wiki/Architecture.md), which identified that the complexity of the original `write.py` (1400+ lines) had become a liability.

## 🏗️ Architectural Pillars

### 1. Modular Pipelines
The monolithic `write.py` has been decomposed into distinct logical domains:

- **ETL (`orchestration/pipelines/etl/`)**: Handles data ingestion, preparation, and privacy filtering. It is purely functional and side-effect free where possible.
- **Execution (`orchestration/pipelines/execution/`)**: The core processing logic that accepts prepared data and orchestrates agents.
- **Coordination (`orchestration/pipelines/coordination/`)**: Manages background tasks, state persistence, and inter-process communication.

### 2. Explicit Configuration
Gone are the "magic numbers" buried deep in conditional logic. The Symbiote architecture enforces explicit configuration via `src/egregora/config/defaults.py`.
- **Single Source of Truth**: All default values (rate limits, window sizes, model names) are centralized.
- **Overridability**: Defaults can be cleanly overridden by runtime configuration without code changes.

### 3. Unified State (Vision)
The system is moving towards a **Pipeline State Machine** that tracks progress not just by "files written" but by logical phases (Initializing, Parsing, Windowing, Processing). This enables:
- **Resumability**: If the pipeline crashes, it knows exactly where it left off.
- **Observability**: The user can query "How far along are we?" and get a precise answer.

### 4. Error Boundaries
The "crash-on-first-error" pattern of the Batch Era is replaced by **Error Boundaries**.
- **Critical Path**: Errors here stop the pipeline (e.g., Database corruption).
- **Non-Critical Path**: Errors here are logged and the item is skipped or flagged (e.g., One bad image link in a chat).

## 🧩 Key Components

### The Orchestrator (`orchestration/`)
The brain of the system. It no longer does the work; it delegates it. It ensures that `ETL` feeds `Execution`, and `Execution` updates `State`.

### The Agents (`agents/`)
Specialized workers that perform discrete cognitive tasks.
- **Writer**: Converts chat windows into narrative posts.
- **Profile**: Updates author profiles based on new evidence.
- **Banner**: Generates visual assets for posts.

### The Sinks (`output_sinks/`)
Pluggable destinations for the generated content. Currently focused on MkDocs, but architected to support Notion, SQL, or other CMSs in the future.

## 📈 Evolution from Batch Era

| Feature | Batch Era (Sprint 1-2) | Symbiote Era (Sprint 3+) |
| :--- | :--- | :--- |
| **Structure** | Monolithic Scripts (`write.py`) | Modular Packages (`etl`, `execution`) |
| **Configuration** | Implicit / Magic Numbers | Explicit `defaults.py` |
| **Failure Mode** | Catastrophic Exit | Graceful Degradation / Retry |
| **State** | Filesystem Artifacts | Unified State Machine |
| **Philosophy** | "Run this script" | "Manage this pipeline" |

## 🔮 Future Direction

The Symbiote Era lays the groundwork for:
- **Multi-Provider Support**: Seamlessly switching between Google Gemini, OpenAI, and Anthropic.
- **Dry-Run Mode**: Estimating costs and tokens before spending a dime.
- **Live Observability**: Real-time dashboards of pipeline progress.
