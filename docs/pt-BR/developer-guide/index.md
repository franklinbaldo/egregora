# Dev Setup

```bash
uv sync && uv run pytest -q
uv run python scripts/process_backlog.py data/whatsapp_zips \
  _tmp_posts --offline --quiet
```

1. **Instale dependências** com `uv sync`.
   O comando usa `pyproject.toml` como fonte única.
2. **Rode os testes rápidos** com `uv run pytest -q`.
   O pacote já carrega fixtures do pipeline.
3. **Smoke test**: processe os ZIPs de exemplo (`tests/data/zips`) apontando
   para uma pasta temporária.
   O resultado deve criar `_tmp_posts/` com Markdown gerado.

## Estrutura do projeto

```mermaid
graph TD
  A[CLI / Typer] --> B[PipelineConfig (Pydantic)]
  B --> C[Parser (Polars)]
  C --> D[Enrichment]
  D --> E[RAG / MCP]
  D --> F[Renderização de Posts]
  B --> G[Cache & Perfis]
```

- O diretório `src/egregora/` contém o pipeline principal.
- `scripts/` guarda utilitários de linha de comando.
- `docs/` é gerado por MkDocs; os posts vivem em `docs/pt-BR/posts/`.

## Como rodar localmente

- Use `uv run egregora --config egregora.toml --days 1` para gerar os posts
  recentes.
- Flags úteis: `--since` (data inicial), `--disable-enrichment`,
  `--disable-profiles`.
- Para experimentar o servidor MCP, habilite `[rag] enabled = true` e rode
  `uv run egregora mcp`.

## Convenções de contribuição

- PRs pequenos (< 400 linhas alteradas) com descrição clara e checklist de
  testes.
- Adicione labels `area:*` e `type:*` ao abrir a PR.
- Atualize a documentação e exemplos quando mudar o comportamento do pipeline.
- Evite código morto: remova flags antigas assim que a migração terminar.

## ADRs & notas

- Consulte o [Índice de ADRs](adr-index.md) para histórico de decisões.
- Análises antigas continuam acessíveis:
  - [CODE_ANALYSIS](CODE_ANALYSIS.md)
  - [PHILOSOPHY](PHILOSOPHY.md)
  - [Plano de refatoração](plan.md)
