# Egregora Roadmap

## 🎯 Project Overview
**Egregora** is a sophisticated local-first pipeline that transforms chat history (e.g., WhatsApp) into rich, narrative-driven static websites. Unlike simple converters, it focuses on "Invisible Intelligence" to generate contextual posts, author profiles, and ranked highlights using LLMs (Google Gemini), DuckDB, and Pydantic-AI.

## 📊 Current State Summary

*   **Strengths**:
    *   **Architecture**: Solid layered design (CLI -> Orchestration -> Agents -> Database) with excellent separation of concerns.
    *   **Data Stack**: Modern, high-performance stack using Ibis + DuckDB for OLAP and LanceDB for vector search.
    *   **Code Quality**: Core orchestration logic (`write.py`) has been recently refactored into modular components. Type safety is enforced via MyPy.
    *   **Extensibility**: Strong patterns for adapters and output sinks.

*   **Weaknesses**:
    *   **Test Suite**: Test execution is currently broken due to missing `playwright` dependency. Coverage is reported low (~39%).
    *   **Vendor Lock-in**: Hard dependency on Google Gemini API for all AI features.
    *   **Documentation gaps**: Missing `CONTRIBUTING.md`, API reference, and deep architecture docs.
    *   **Configuration**: Defaults are sometimes hardcoded or scattered; lack of a dry-run mode for cost estimation.

*   **Technical Debt**:
    *   Implicit magic numbers in windowing logic.
    *   Missing unified pipeline state management (state is distributed).

*   **Test Coverage**: Low (~39%). Critical paths in orchestration and RAG integration need better coverage.

## 🚀 Roadmap (Prioritized)

### Phase 1: Critical Fixes & Stability (Next 2 weeks)
- [ ] **Fix Test Suite Dependency**
    - **Why**: Tests are failing to collect due to missing `playwright`.
    - **Impact**: Enables reliable CI/CD and contribution.
    - **Effort**: S
    - **Dependencies**: None
- [ ] **Create CONTRIBUTING.md**
    - **Why**: Critical entry point for new developers is missing.
    - **Impact**: Unblocks open source contributions and standardize workflows.
    - **Effort**: S
    - **Dependencies**: None
- [ ] **Establish Error Boundary Pattern**
    - **Why**: Error handling is currently inconsistent (some fatal, some silent).
    - **Impact**: Predictable failure modes and better user feedback.
    - **Effort**: M
    - **Dependencies**: None

### Phase 2: Core Features (Next month)
- [ ] **Multi-Provider Support (OpenAI Fallback)**
    - **Why**: Eliminate single point of failure (Google Gemini) and vendor lock-in.
    - **Impact**: Increased resilience and flexibility for users.
    - **Effort**: L
    - **Dependencies**: `config/settings.py` refactor
- [ ] **Dry-Run Mode**
    - **Why**: Users need to estimate costs and validate input before running expensive LLM pipelines.
    - **Impact**: Improved user trust and UX.
    - **Effort**: M
    - **Dependencies**: None
- [ ] **Centralize Configuration Defaults**
    - **Why**: Eliminate magic numbers and scattered config defaults.
    - **Impact**: Easier maintainability and clearer configuration discovery.
    - **Effort**: S
    - **Dependencies**: None
- [ ] **Generate API Documentation**
    - **Why**: Developer documentation is missing API references.
    - **Impact**: Improved developer experience.
    - **Effort**: M
    - **Dependencies**: `mkdocstrings` configuration

### Phase 3: Advanced Features (Next quarter)
- [ ] **Pipeline State Machine**
    - **Why**: Current state is distributed; difficult to track progress or resume.
    - **Impact**: robust resume capabilities and better progress reporting.
    - **Effort**: L
    - **Dependencies**: None
- [ ] **Observability & Metrics**
    - **Why**: Lack of visibility into performance (time per window, token usage).
    - **Impact**: Ability to optimize performance and cost.
    - **Effort**: M
    - **Dependencies**: None
- [ ] **Expand Architecture Documentation**
    - **Why**: Current architecture docs are too brief.
    - **Impact**: Better onboarding and system understanding.
    - **Effort**: M
    - **Dependencies**: None

### Phase 4: Future Vision (6+ months)
- [ ] **GUI / Admin Panel**
    - **Why**: Lower barrier to entry for non-technical users.
- [ ] **Real-time / Incremental Updates**
    - **Why**: Support continuous chat ingestion without full reprocessing.
- [ ] **Plugin System Marketplace**
    - **Why**: Allow community to share custom adapters and skills.

## 💡 Quick Wins
- **Fix `ADR` Numbering**: Duplicate `0004` ADRs cause confusion.
- **Add FAQ Section**: Reduce repetitive questions by documenting common issues.
- **Lint Docstrings**: Enforce docstring presence to improve code documentation coverage.

## 🔧 Technical Improvements Backlog
- **Refactor `runner.py`**: While `write.py` is improved, `runner.py` still holds significant logic that could be decomposed.
- **Integration Tests for RAG**: Add specific tests for the vector store and embedding integration.
- **Performance Profiling**: Add benchmarks to CI to catch regressions.

## 📝 Documentation Needs
- **API Reference**: Auto-generate from docstrings.
- **Troubleshooting Guide**: Comprehensive guide for common errors (429s, DB locks).
- **Examples**: specific "How-to" guides (e.g., "WhatsApp to Blog", "Custom Adapter").

## 🧪 Testing Gaps
- **Playwright/E2E**: Verify privacy features and frontend generation.
- **RAG Integration**: Verify semantic search relevance and fallback behavior.
- **Database Persistence**: Verify idempotency and data integrity in edge cases.

## 🎨 Innovation Ideas
- **Voice-to-Text Adapter**: Ingest audio messages directly.
- **Video Highlights**: Generate video montages from shared media.
- **Interactive Timelines**: New visualization for the static site.
