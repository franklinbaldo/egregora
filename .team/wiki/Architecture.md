# 🏗️ Architecture & Core

> **Current Status:** [The Symbiote Era](Architecture-Symbiote-Era.md) (Sprint 3+)
> **Previous Status:** [The Batch Era](Architecture-Batch-Era.md) (Sprint 1-2)

This document serves as the high-level entry point for the **Egregora** system architecture.

## 🧬 Current Paradigm: The Symbiote Era

As of **Sprint 3 (January 2026)**, the system operates under the **Symbiote** architecture.

**Key Characteristics:**
- **Modular Pipelines:** Separation of ETL, Execution, and Coordination.
- **Explicit Configuration:** Centralized defaults in `defaults.py`.
- **Unified State:** In-memory `PipelineContext` replacing ad-hoc parameter passing.
- **Resilience:** Item-level error boundaries and sophisticated recovery strategies.

👉 **[Read the Full Symbiote Architecture](Architecture-Symbiote-Era.md)**

---

## 🏛️ Historical Context: The Batch Era

During **Sprint 1 and 2**, the system was bootstrapped as a "Batch Processing Engine". This era established the foundational concepts of Windows, Enriched Data, and Journaling.

**Key Characteristics:**
- **Monolithic Scripts:** `write.py` handled all logic.
- **CLI-Driven:** Run-once execution model.
- **Recursive Splitting:** Handling token limits via recursion.

👉 **[Read the Batch Era Archive](Architecture-Batch-Era.md)**

---

## 📚 Core Documentation

### [Glossary](Glossary.md)
Definitions of ubiquitous language (Window, Artifact, Persona, etc.).

### [Protocols & Workflows](Protocols.md)
Standard operating procedures for contributors and agents.
