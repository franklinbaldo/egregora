# User Stories from Open Pull Requests

This report consolidates actionable ideas and features from open Pull Requests into detailed User Stories, focusing on items not yet present in the `main` branch.

## 1. Mock Writer Mode for Offline Development
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
- Modify the `Writer` agent initialization in `src/egregora/agents/writer.py` to check the env var.
- Inject a "MockModel" or "MockStrategy" that returns pre-defined `AgentRunResult` objects.

---

## 2. Enhanced Homepage with Rich Post Links
**Source PRs:** #2032

**User Story:**
As a **Site Visitor**,
I want to **see rich previews of recent *posts* on the homepage (including titles, dates, and summaries) in addition to media**,
So that **I can discover the latest written content immediately upon landing.**

**Acceptance Criteria:**
- [ ] **Data Injection:** The `SiteGenerator.regenerate_main_index` method must retrieve recent `DocumentType.POST` items (not just Media).
- [ ] **Context Update:** Pass this list of post objects to the index Jinja template context.
- [ ] **Template Rendering:** Update `index.md.jinja` (or `index.html`) to render these posts as semantic cards or a list with summaries.
- [ ] **Permalinks:** Ensure the generated links point correctly to the post permalinks.

**Implementation Notes:**
- Extend `SiteGenerator` in `src/egregora/output_adapters/mkdocs/site_generator.py` to include a `get_recent_posts(limit=5)` method.
- Update the `context` dictionary in `regenerate_main_index` to include `recent_posts`.

---

## 3. Codebase Modularization: Decoupling and Refactoring
**Source PRs:** #2029, #2023

**User Story:**
As a **Developer**,
I want to **refactor specific components into dedicated modules**,
So that **the codebase adheres to the Single Responsibility Principle and is easier to maintain.**

**Acceptance Criteria:**
- [ ] **Filesystem Utils:** Move post-writing logic (file I/O, frontmatter dumping) from generic `src/egregora/utils/` to a new `src/egregora/output_adapters/mkdocs/writing.py` module.
- [ ] **RAG Types:** Move the `RAGChunk` dataclass from `src/egregora_v3/infra/rag.py` to `src/egregora_v3/core/types.py` (or `rag/types.py`) to decouple the core data definition from the infrastructure implementation.

**Implementation Notes:**
- Create `src/egregora/output_adapters/mkdocs/writing.py` and migrate relevant functions.
- Move `RAGChunk` definition and update imports.

---

## 4. Refactor Orchestration Runner
**Source PRs:** #2016, #2010

**User Story:**
As a **Developer**,
I want to **simplify the `PipelineRunner` class by extracting complex logic into smaller helper methods**,
So that **the main orchestration loop is readable, testable, and less prone to bugs.**

**Acceptance Criteria:**
- [ ] **Reduce Complexity:** Refactor `_process_single_window` to reduce its cyclomatic complexity.
- [ ] **Extract Command Processing:** Move command extraction/filtering logic into a dedicated method or class.
- [ ] **Extract Status Messaging:** separate status message generation from core logic.
- [ ] **Configuration:** Externalize hardcoded magic numbers (e.g., token limits) to configuration files.

**Implementation Notes:**
- Address the `TODO: [Taskmaster]` comments present in `src/egregora/orchestration/runner.py`.
