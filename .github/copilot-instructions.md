# Copilot instructions for Egregora

Use this file to give short, practical guidance for AI coding agents working on the Egregora repository.
Keep advice concrete and tied to the codebase (commands, important files, patterns).

- Big picture: Egregora converts WhatsApp export .zip files into Markdown newsletters, enriquece links com Gemini e mantém um RAG acessível via MCP. Main execution path: CLI entrypoint `egregora` (console script -> `src/egregora/__main__.py`) chama `src/egregora/pipeline.py`, que orquestra anonimização, enriquecimento opcional (`src/egregora/enrichment.py`), buscas RAG (`src/egregora/rag/*`) e escreve `newsletters/YYYY-MM-DD.md`.

- Where to look first:
  - `README.md` / `PHILOSOPHY.md` — visão geral do projeto, exemplos de execução e contexto filosófico.
  - `pyproject.toml` — entry point (`egregora.__main__:run`) and dependency hint (requires `google-genai`).
  - `src/egregora/pipeline.py` — core orchestration and CLI-config translation (how flags map to `PipelineConfig`).
  - `src/egregora/enrichment.py` — enrichment flow, caching, and Gemini-specific usage (uses `types.Part.from_uri`).
  - `src/egregora/cache_manager.py` — JSON-based persistent cache semantics and UUID normalization for URLs.
  - `src/egregora/anonymizer.py` — deterministic anonymization rules (phone normalization, three formats: `human`, `short`, `full`).
  - `src/egregora/mcp_server/` — MCP server exposing RAG tools (optional `mcp` dependency).

- Important runtime flags & defaults (copy behavior from `__main__.py` and `config.py`):
  - CLI: `uv run egregora` (project uses `uv` for virtualenv/devenv). Alternate: `python -m egregora.__main__` in a pip-installed environment.
  - Key flags: `--enable-enrichment`, `--disable-enrichment`, `--relevance-threshold`, `--max-enrichment-items`, `--max-enrichment-time`, `--cache-dir`, `--disable-cache`, `--disable-anonymization`, `--double-check-newsletter`.
  - Defaults: enrichment enabled, cache enabled at `cache/`, anonymization enabled (`human` format), default Gemini model `gemini-flash-lite-latest`.

- Tests & quick checks:
  - Small smoke: `python example_enrichment.py` (honors `GEMINI_API_KEY` env var) to validate enrichment.
  - Unit tests live under `tests/` (pytest). Running tests depends on environment; ensure dependencies installed via `uv sync` or `pip` then run `pytest`.

- Common coding patterns and conventions to follow in edits:
  - Defensive optional dependencies: many modules import `mcp` and `google.genai` inside try/except. When adding code that uses those libs, guard with the same pattern and provide sensible fallbacks or clear runtime errors.
  - Config is centralized in `src/egregora/config.py` and constructed via `PipelineConfig.with_defaults()`; prefer updating config objects rather than scattering magic constants.
  - Cache keys: `CacheManager.generate_uuid(url)` normalizes URLs deterministically — use it when interacting with cache files.
  - Anonymization: use `Anonymizer.anonymize_author()` (accepts phones and nicknames) and respect `PipelineConfig.anonymization.output_format`.
  - LLM usage expects JSON responses for enrichment; `ContentEnricher._parse_response` parses `json.loads` of model output. When changing prompts, keep JSON schema stable.

- Integration & I/O surfaces that matter for PRs:
  - External dependencies: `google-genai` (Gemini) — network calls and API key (`GEMINI_API_KEY`). Cache reduces calls.
  - MCP integration: optional `mcp` package exposes the RAG via Model Context Protocol; the RAG code uses local index files under `cache/rag`.
  - Filesystem layout: input zips under `data/whatsapp_zips/`; generated newsletters under `newsletters/`; enrichment cache in `cache/analyses` and index at `cache/index.json`.

- Debugging tips specific to this repo:
  - If LLM client missing, code raises helpful RuntimeError messages (search for "a depend\u00eancia opcional" or check `try/except ModuleNotFoundError` blocks).
  - To reproduce anonymization output quickly, call `discover` subcommand: `python -m egregora.__main__ discover "+5511999999999"`.
  - To run the MCP RAG server locally: ensure `mcp` installed, then `python scripts/start_mcp_server.py` or `uv run python -m egregora.mcp_server.server`.

- Safety & secrets:
  - Do not hardcode API keys. The code expects `GEMINI_API_KEY` env var. When writing tests/mocks, patch `genai` clients or inject a fake client.
  - The repository intentionally anonymizes personal data; when editing text that touches prompts or anonymization logic, preserve privacy safeguards and the `REVIEW_SYSTEM_PROMPT` used in `pipeline.py`.

- Small examples to reference in edits:
  - Prompt JSON for enrichment in `src/egregora/enrichment.py` (method `_build_prompt`). Keep keys `summary`, `key_points`, `tone`, `relevance`.
  - Cache usage example: `CacheManager.set(url, payload)` and `CacheManager.get(url)` in `enrichment.py`.

If anything below is unclear or you need access to private config (CI, external keys, or a preferred local test dataset), ask the maintainers before making changes.

## Features implementadas (2025-10-03)

- ✅ Enriquecimento multimodal usando Gemini (links, PDFs, YouTube, imagens).
- ✅ Cache persistente de análises (`cache_manager.py`).
- ✅ Sistema RAG completo (`src/egregora/rag/`) com ferramentas MCP.
- ✅ Servidor MCP (`src/egregora/mcp_server/`) pronto para Claude Desktop.
- ✅ Anonimização determinística e ferramentas de autodescoberta.
- 🔄 Migração para embeddings do Gemini (opcional, em validação).

## Roadmap atualizado

### Em andamento
- Migrar índice TF-IDF para `gemini-embedding-001` com cache dedicado.
- Adicionar suíte de testes automatizados para o servidor MCP.
- Benchmark de performance comparando TF-IDF x embeddings.

### Não planejado
- ❌ Dependências externas de parsing (`pdfplumber`, `yt-dlp`).
- ❌ Batching agressivo de chamadas LLM (complexidade alta, ganho marginal).
- ❌ Pipelines paralelos específicos para cada tipo de mídia (Gemini já cobre os casos principais).
