# Egregora Agent Guide (`AGENTS.md`)

> **Note to AI Agents:** This file is your primary source of truth for working within the Egregora codebase. Read it carefully before planning or executing tasks.

## 1. Core Architecture & Philosophy

Egregora is an **"Emergent Group Reflection Engine"**. It transforms raw chat logs (WhatsApp) into a structured, privacy-first blog using a multi-stage pipeline.

### The "Tenets" (Non-Negotiables)
1.  **Ibis Everywhere:** All data transformations must happen via `ibis` expressions on DuckDB tables. Avoid converting to pandas/python lists unless absolutely necessary for a final sink.
2.  **Synchronous Core:** The core pipeline is **synchronous**. Do not use `asyncio` for the main orchestration logic. We use `ThreadPoolExecutor` for concurrency (e.g., in `BannerWorker`).
3.  **Privacy First:** PII is stripped *before* it leaves the `InputAdapter`. Real names never touch the LLM.
4.  **Parse, Don't Validate:** Trust internal data contracts. Don't add defensive `if x is None` checks deep in the pipeline if the schema guarantees existence.
5.  **XDG-Aware:** We store data in `~/.egregora/`, not the local directory (except for the `output/` site).

### Directory Structure
- `src/egregora/orchestration/`: The "Brain". Pipelines, contexts, and high-level logic.
- `src/egregora/agents/`: The "Workers". Specific logic for Writing, Enrichment, Avatars.
- `src/egregora/database/`: The "Memory". Ibis schemas (`ir_schema.py`) and storage managers.
- `src/egregora/input_adapters/`: The "Senses". Parsers for WhatsApp, etc.
- `src/egregora/output_adapters/`: The "Voice". MkDocs site generation.

---

## 2. Development & Testing Workflow

### Dependency Management
- We use **`uv`** for everything.
- **Install:** `uv sync --all-extras`
- **Run CLI:** `uv run egregora ...`
- **Run Tests:** `uv run pytest`

### Testing Strategy
1.  **Golden Fixtures:** We rely heavily on VCR cassettes (`tests/fixtures/vcr_cassettes`) and "Golden" outputs.
    - If you break a golden test, **verify if the change is intentional**. If so, update the golden files.
2.  **E2E Tests:** Located in `tests/e2e/`. These are the most critical.
    - Run specific E2E: `uv run pytest tests/e2e/test_extended_e2e.py`
3.  **Mocking:** Use `unittest.mock` or `pytest.monkeypatch`. For LLM calls, use the established patterns in `tests/conftest.py` (e.g., `mock_gemini_client`).

### Common Pitfalls
- **Async/Sync Mixing:** Don't call `asyncio.run()` inside a function that is already running in an event loop (though our core is sync, some libraries might use async internally).
- **Path Handling:** Always use `pathlib.Path`. Never use string concatenation for paths.
- **Dependency Drift:** Always run `uv sync` if you suspect dependencies are out of sync.

---

## 3. Dealing with LLMs & Agents

- **Pydantic AI:** We use `pydantic-ai` for agent logic. Models are defined in `src/egregora/agents/`.
- **Model Fallbacks:** We support multiple models (`gemini-2.0-flash`, `gemini-1.5-pro`, etc.). If a model is deprecated, update `src/egregora/config/settings.py` and `src/egregora/utils/model_fallback.py`.
- **Prompting:** Prompts are stored as Jinja2 templates in `src/egregora/prompts/`. Do not hardcode prompts in Python files.

---

## 4. UI/UX & Documentation

- **MkDocs:** The site is generated using MkDocs Material.
- **Customization:** Logic lives in `src/egregora/output_adapters/mkdocs/`.
- **Theme Overrides:** `src/egregora/rendering/templates/site/theme/`.
- **CSS/JS:** `src/egregora/rendering/templates/site/stylesheets/` and `javascripts/`.

---

## 5. How to Fix Bugs (Heuristic)

1.  **Reproduce:** Create a minimal reproduction case or identifying the failing test.
2.  **Locate:** Use `grep` or file listings to find the relevant code. Trust the module structure.
3.  **Fix:** Apply the fix.
4.  **Verify:** Run the specific test *and* related E2E tests.
5.  **Reflect:** Did this break a tenet? (e.g., did I add a pandas dependency? Did I make it async?)

---

**Remember:** You are an expert engineer. Write clean, typed, and documented code. If you are unsure, check `pyproject.toml` for dependencies and `src/egregora/config/settings.py` for configuration sources.
