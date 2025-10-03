# Guia de Migração do Egregora

Este guia resume as principais mudanças entre versões e orienta upgrades seguros.

## V1 → V2 — Enriquecimento de Conteúdo

**Novidades**

- Módulo `ContentEnricher` com suporte nativo do Gemini (`Part.from_uri`).
- Cache persistente das análises (`cache_manager.py`).
- Flags dedicadas na CLI (`--enable-enrichment`, `--relevance-threshold`, `--max-enrichment-items`).

**Ação recomendada**

- Nenhuma migração obrigatória. Apenas execute `uv sync` para atualizar dependências.
- Revise `ENRICHMENT_QUICKSTART.md` para ativar o módulo se desejar.

## V2 → V3 — RAG + Embeddings Gemini (Opcional)

**Novidades**

- RAG consolidado em `src/egregora/rag/` com integração MCP (`src/egregora/mcp_server/`).
- Flag `--use-gemini-embeddings` para substituir TF-IDF por embeddings semânticos.
- Cache de embeddings persistente em `cache/embeddings/`.

**Passos para habilitar embeddings**

```bash
# 1. Reindexar com embeddings
uv run egregora --use-gemini-embeddings --force-reindex

# 2. Verificar cache gerado
ls cache/embeddings/

# 3. Uso regular com embeddings
uv run egregora --use-gemini-embeddings
```

**Compatibilidade**

- ✅ TF-IDF permanece disponível como fallback automático.
- ✅ Ambas as abordagens podem compartilhar o mesmo diretório `cache/`.
- ✅ MCP server detecta automaticamente a estratégia ativa.

**Quando não habilitar embeddings**

- Ambientes sem acesso ao modelo `gemini-embedding-001`.
- Pipelines onde custo adicional não traz ganho significativo.

## Deprecações

- Nenhuma funcionalidade removida até a V3.
- Planejamento de futuro aviso se o TF-IDF for descontinuado (mínimo 6 meses).

*Última atualização: 2025-10-03*
