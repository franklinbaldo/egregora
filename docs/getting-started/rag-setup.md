---
title: Configurar RAG Local
description: Como preparar e aproveitar o índice DuckDB+Gemini do pipeline 1.0.
---

# Configurar o RAG Local

A versão 1.0 do Egregora combina embeddings Gemini com DuckDB para oferecer busca
contextual instantânea durante a geração de posts. Este guia explica como
habilitar o índice vetorial, consultar trechos históricos e reutilizar o
servidor FastMCP.

## Pré-requisitos

1. **Credenciais Gemini** – configure `GEMINI_API_KEY` ou `GOOGLE_API_KEY`
   com acesso ao modelo `models/embedding-001`.
2. **Exports do WhatsApp** – organize os arquivos `.zip` em um diretório como
   `data/exports/`.
3. **Ambiente Python 3.12** – instale as dependências com `uv sync --extra
   docs --extra test`.

## Geração do índice

Execute o pipeline completo apontando para os exports desejados:

```bash
uv run egregora pipeline data/exports/*.zip --days 3 --workspace .cache/pipeline
```

O comando executa as seguintes etapas:

1. **Ingestão e anonimização** – o módulo `ingest_exports` consolida os exports
   em um único `DataFrame` e aplica pseudônimos determinísticos através do
   `Anonymizer`.
2. **Embeddings Gemini** – `embed_dataframe` cria a coluna vetorial usando
   `GeminiEmbedder` e salva o resultado em Parquet.
3. **RAG em memória** – `build_local_rag_client` inicializa um índice
   DuckDB/HNSW que responde a consultas de similaridade.
4. **Geração de posts** – `_run_generation` injeta snippets no template Jinja
   e produz Markdown pronto para MkDocs.

## Visualizar snippets recuperados

Por padrão, o pipeline injeta trechos similares nas chamadas ao modelo. Para
inspecionar o que foi utilizado basta ativar a flag `--show`:

```bash
uv run egregora pipeline data/exports/*.zip --days 1 --show
```

O terminal exibirá as posts e uma tabela com os trechos retornados pelo RAG.

## Executar o servidor FastMCP

Se preferir separar a etapa de busca, inicie o servidor FastMCP manualmente:

```bash
uv run egregora rag serve embeddings.parquet --port 8000
```

Depois, reutilize o endpoint no pipeline principal:

```bash
uv run egregora pipeline data/exports/*.zip --rag-endpoint http://localhost:8000 --no-inject-rag
```

Com essa abordagem, o pipeline apenas consome o servidor externo, ideal para
compartilhar o índice com outras aplicações.

## Próximos passos

- Ajuste `--rag-top-k` e `--rag-min-similarity` para calibrar a quantidade de
  contexto.
- Use `--archive` para enviar o Parquet ao Internet Archive e carregar o índice
  em execuções futuras.
