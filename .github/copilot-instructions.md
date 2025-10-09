# Copilot instructions for Egregora

Use this file to give short, practical guidance for AI coding agents working on the Egregora repository.
Keep advice concrete and tied to the codebase (commands, important files, patterns).

- Big picture: Egregora converts WhatsApp export .zip files into Markdown posts, enriquece links com Gemini e mantém um RAG acessível via MCP. Main execution path: CLI entrypoint `egregora` (console script -> `src/egregora/__main__.py`) instancia `UnifiedProcessor` (`src/egregora/processor.py`), que orquestra anonimização, enriquecimento opcional (`src/egregora/enrichment.py`), buscas RAG (`src/egregora/rag/*`) e escreve `data/posts/<grupo>/daily/YYYY-MM-DD.md`.

- Where to look first:
  - `README.md` / `PHILOSOPHY.md` — visão geral do projeto, exemplos de execução e contexto filosófico.
  - `pyproject.toml` — entry point (`egregora.__main__:run`) and dependency hint (requires `google-genai`).
  - `src/egregora/processor.py` — core orchestration for the Polars-native pipeline (discovers groups, enriches, renders, writes posts).
  - `src/egregora/pipeline.py` — prompt loaders, transcript anonymisation helpers, and ZIP/text utilities kept for testing.
  - `src/egregora/enrichment.py` — enrichment flow, caching, and Gemini-specific usage (uses `types.Part.from_uri`).
  - `src/egregora/cache_manager.py` — JSON-based persistent cache semantics and UUID normalization for URLs.
  - `src/egregora/anonymizer.py` — deterministic anonymization rules (phone normalization, three formats: `human`, `short`, `full`).
  - `src/egregora/mcp_server/` — MCP server exposing RAG tools (optional `mcp` dependency).
  - `src/egregora/backlog/` — scanners, checkpointing and batch processor used by the backlog scripts.

- Important runtime flags & defaults (copy behavior from `__main__.py` and `config.py`):
  - CLI: `uv run egregora` (project uses `uv` for virtualenv/devenv). Alternate: `python -m egregora.__main__` in a pip-installed environment.
  - Key flags: `--enable-enrichment`, `--disable-enrichment`, `--relevance-threshold`, `--max-enrichment-items`, `--max-enrichment-time`, `--cache-dir`, `--disable-cache`, `--disable-anonymization`, `--double-check-post`.
  - Defaults: enrichment enabled, cache enabled at `cache/`, anonymization enabled (`human` format), default Gemini model `gemini-flash-lite-latest`.
- Batch tooling: use `scripts/process_backlog.py` (flags `--scan`, `--dry-run`, `--resume`, `--skip-enrichment`, `--force-rebuild`) and `scripts/backlog_post.py` for monitoring. Both rely on `BacklogProcessor` and respect `scripts/backlog_config.yaml`.

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
- Filesystem layout: input zips under `data/whatsapp_zips/`; generated posts under `data/posts/<slug>/daily/`; enrichment cache em `cache/analyses` e índice em `cache/index.json`.

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

## 🚀 Caminho Principal (Quick Start)

**Para usuários:**
1. Coloque os exports `.zip` do WhatsApp em `data/whatsapp_zips/`.
2. Rode `python scripts/process_backlog.py data/whatsapp_zips data/posts` para processar o backlog completo.
3. As posts do dia ficam em `data/posts/<grupo>/daily/YYYY-MM-DD.md`.

**Para CI/CD:**
1. `tools/build_posts.py` agrega `data/posts/` em coleções no diretório `docs/<lang>/posts/`.
2. `mkdocs build --strict` gera o site estático.
3. O workflow `gh-pages.yml` publica tudo no GitHub Pages.

**Entrypoints úteis:**
- CLI interativo: `uv run egregora` (usa `PipelineConfig.with_defaults`).
- Processamento em lote: `python scripts/process_backlog.py` (diretórios explícitos).
- Servidor MCP/RAG: `python scripts/start_mcp_server.py` (dependência opcional `mcp`).

If anything below is unclear or you need access to private config (CI, external keys, or a preferred local test dataset), ask the maintainers before making changes.

## Features implementadas (2025-10-03)

- ✅ Enriquecimento multimodal usando Gemini (links, PDFs, YouTube, imagens).
- ✅ Cache persistente de análises (`cache_manager.py`).
- ✅ Sistema RAG completo (`src/egregora/rag/`) com ferramentas MCP.
- ✅ Servidor MCP (`src/egregora/mcp_server/`) pronto para Claude Desktop.
- ✅ Anonimização determinística e ferramentas de autodescoberta.
- ✅ Migração definitiva para embeddings do Gemini como mecanismo único de busca.

## Roadmap atualizado

### Em andamento
- Monitorar desempenho do índice baseado em embeddings e ajustar parâmetros conforme necessário.
- Adicionar suíte de testes automatizados para o servidor MCP.
- Benchmark de performance comparando TF-IDF x embeddings.

### Não planejado
- ❌ Dependências externas de parsing (`pdfplumber`, `yt-dlp`).
- ❌ Batching agressivo de chamadas LLM (complexidade alta, ganho marginal).
- ❌ Pipelines paralelos específicos para cada tipo de mídia (Gemini já cobre os casos principais).
