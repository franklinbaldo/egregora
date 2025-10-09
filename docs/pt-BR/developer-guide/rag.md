# RAG

O módulo de Retrieval-Augmented Generation (RAG) transforma os posts em um
índice vetorial consultável.
Ele alimenta tanto o servidor MCP quanto buscas internas para responder
perguntas sobre o histórico.

## Fluxo

1. `PostRAG` carrega posts em Markdown a partir de `posts_dir`.
2. Cada documento é fatiado com `TokenTextSplitter`
   (chunks de ~1800 tokens, overlap 360).
3. Geramos embeddings com `CachedGeminiEmbedding`
   (modelo `models/gemini-embedding-001`).
4. Os vetores vão para `SimpleVectorStore`, persistidos em `cache/embeddings/`.
5. Buscas chamam `rag.search(query, top_k, min_similarity)` e retornam
   `NodeWithScore`.

## Parâmetros principais

- `enabled` (`false`) — ativa o pipeline ao carregar `PipelineConfig` ou rodar
  `egregora mcp`.
- `embedding_model` (`models/gemini-embedding-001`) — nome do modelo Gemini
  usado para gerar vetores.
- `embedding_dimension` (`768`) — dimensão esperada pelo vector store.
- `top_k` (`5`) — quantidade padrão de chunks retornados por busca.
- `min_similarity` (`0.65`) — score mínimo para considerar um chunk relevante.
- `export_embeddings` (`false`) — quando `true`, gera Parquet em
  `embedding_export_path`.

Todos os campos vivem em `[rag]` no `egregora.toml`.

## Uso rápido

```toml
[rag]
enabled = true
export_embeddings = true
embedding_export_path = "artifacts/embeddings/post_chunks.parquet"
```

```python
from pathlib import Path
from egregora.rag import PostRAG
from egregora.config import PipelineConfig

config = PipelineConfig.from_toml(Path("egregora.toml"))
rag = PostRAG(posts_dir=Path("data"), cache_dir=Path("cache"), config=config.rag)
rag.update_index(force_rebuild=True)
print(rag.search("decisões sobre eventos", top_k=3))
```

## Servidor MCP

- Com `rag.enabled = true`, rode `uv run egregora mcp`.
- Ferramentas disponíveis: `search_posts`, `generate_search_query`, `get_post`,
  `list_posts`, `get_rag_stats`, `reindex_posts`.
- Recursos `post://AAAA-MM-DD` expõem o Markdown bruto para clientes MCP.

## Boas práticas

- Configure `GOOGLE_API_KEY` para obter embeddings reais; sem a chave o fallback
  determinístico mantém o fluxo funcionando.
- Rode `rag.update_index(force_rebuild=True)` após importar um lote grande de
  posts.
- No CI, combine com o passo “Build RAG embeddings artifact” para publicar o
  Parquet.
