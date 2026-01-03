# User Stories from Open Pull Requests

This report consolidates actionable ideas and features from open Pull Requests into detailed User Stories.

## 1. Optimize and Consolidate Gemini Automation
**Source PRs:** #2037, #2036, #2035, #2034, #2033, #2031

**User Story:**
As a **DevOps Engineer / Repository Maintainer**,
I want to **consolidate the Gemini-based PR review, merge gate, and rewriter workflows into a single, efficient process**,
So that **I can reduce API costs/latency, simplify CI configuration, and leverage the latest Gemini models (e.g., Gemini 2.0/3.0) for better accuracy.**

**Acceptance Criteria:**
- [ ] **Single Invocation:** The PR review pipeline must make exactly *one* call to the Gemini API per execution, requesting a structured JSON response that includes:
    - Code Review feedback (bugs, security).
    - Merge Decision (Approve/Request Changes).
    - PR Rewrite suggestions (title, body).
- [ ] **Unified Workflow:** Replace separate GitHub Actions jobs (review, merge-gate, rewriter) with a single `gemini-pr-review` workflow that handles all outputs.
- [ ] **Model Prioritization:** The system must default to using the latest efficient models (e.g., `gemini-2.0-flash` or `gemini-3.0-preview` if available) before falling back to older stable models.
- [ ] **Diagnostics:** The workflow must output clear diagnostics about which model was used and the latency/cost of the consolidated run.
- [ ] **Documentation:** Update `GEMINI_PR_REVIEW.md` to reflect the single-pass architecture and JSON schema.

**Implementation Notes:**
- Refactor `gemini-pr-review.yml` to use a single prompt.
- Update the system prompt to explicitly request the consolidated JSON schema.
- Ensure the runner script parses the JSON and sets multiple GitHub Actions outputs/comments based on the single response.

---

## 2. Mock Writer Mode for Offline Development
**Source PRs:** #2032

**User Story:**
As a **Developer**,
I want to **run the `egregora write` command in a "Mock Mode" without a valid Gemini API key**,
So that **I can test the pipeline orchestration, file generation, and UI rendering locally or in CI environments where API access is restricted or costly.**

**Acceptance Criteria:**
- [ ] **Environment Variable:** The system must respect a new environment variable `EGREGORA_USE_MOCK_WRITER=1`.
- [ ] **Bypass LLM:** When enabled, the `Writer` agent must *not* attempt to connect to Google Gemini.
- [ ] **Placeholder Content:** The agent must generate valid `Document` objects with placeholder titles, summaries, and body content (e.g., "Lorem Ipsum" or hardcoded templates).
- [ ] **Pipeline Success:** The full write pipeline (parsing -> "generation" -> output) must complete successfully, producing valid Markdown files that MkDocs can build.

**Implementation Notes:**
- Modify the `Writer` agent initialization to check the env var.
- Inject a "MockModel" or "MockStrategy" that returns pre-defined `AgentRunResult` objects.

---

## 3. Enhanced Homepage with Rich Post Links
**Source PRs:** #2032

**User Story:**
As a **Site Visitor**,
I want to **see rich previews of recent posts on the homepage (including titles, dates, and summaries) instead of just generic links**,
So that **I can better decide what to read next.**

**Acceptance Criteria:**
- [ ] **Data Injection:** The `site_generator` must pass full `Document` or `Post` objects to the homepage Jinja template, not just paths or simple dicts.
- [ ] **Template Rendering:** The homepage template must use these objects to render semantic HTML (e.g., `<article>` cards) with correct Markdown links to the posts.
- [ ] **Fix Broken Links:** Ensure that links generated on the homepage correctly resolve to the permalinks of the actual posts.

---

## 4. Codebase Modularization and Decoupling
**Source PRs:** #2029, #2024, #2023, #2017

**User Story:**
As a **Developer**,
I want to **refactor core utilities and types into dedicated modules**,
So that **the codebase adheres to the Single Responsibility Principle, reducing circular dependencies and making specific components (like Atom serialization or RAG chunking) easier to test and reuse.**

**Acceptance Criteria:**
- [ ] **Filesystem Utils:** Move post-writing logic from generic `src/egregora/utils/` to `src/egregora/output_adapters/mkdocs/writing.py`.
- [ ] **Atom Serialization:** Create a dedicated Atom serializer class/module, removing `to_atom()` logic from the core `Document`/`Entry` data types.
    - *Fix:* Ensure user-defined categories are correctly serialized.
- [ ] **RAG Types:** Move `RAGChunk` dataclass from `ingestion.py` to `src/egregora_v3/core/types.py` (or a dedicated `rag/types.py`).
- [ ] **Datetime Utils:** Centralize date extraction and formatting logic into `src/egregora/utils/datetime_utils.py`.

---

## 5. Robust Slugification Testing
**Source PRs:** #2019

**User Story:**
As a **Developer**,
I want to **have a comprehensive test suite for the `slugify` utility**,
So that **I can guarantee consistent URL generation across different inputs and avoid broken links due to regressions in character handling.**

**Acceptance Criteria:**
- [ ] **Test Coverage:** Add unit tests covering edge cases for `slugify` (e.g., non-ASCII characters, mixed case, punctuation, empty strings).
- [ ] **Fix Regressions:** Identify and fix any existing tests (like `simple_chunk_text`) that rely on incorrect slugification or chunking behavior.
