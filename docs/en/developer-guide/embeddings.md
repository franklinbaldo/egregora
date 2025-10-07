# Recuperação Semântica com Gemini Embeddings

O módulo de RAG (Retrieval-Augmented Generation) do Egrégora indexa as
newsletters em um vetor store usando embeddings do Gemini fornecidos pelo
[LlamaIndex](https://www.llamaindex.ai/). Este documento resume o fluxo atual,
os pontos de configuração disponíveis e como habilitar a funcionalidade quando
ela for necessária.

---

## 🧠 Visão Geral do Fluxo

1. `NewsletterRAG` (`src/egregora/rag/index.py`) carrega ou cria um índice
   vetorial persistente em `cache/vector_store/`.
2. As newsletters (`*.md`) são quebradas em chunks com `TokenTextSplitter` e
   inseridas no índice.
3. As buscas executam similaridade semântica via `VectorIndexRetriever`, com
   filtros para ignorar dias muito recentes conforme configuração.
4. Os embeddings são gerados por `CachedGeminiEmbedding`
   (`src/egregora/rag/embeddings.py`), que usa a API oficial do Gemini quando a
   variável `GOOGLE_API_KEY` está presente e recorre a um fallback determinístico
   offline quando não está.

---

## ⚙️ Configuração

A classe `RAGConfig` controla todo o comportamento. Os campos mais relevantes
são:

| Campo                   | Padrão                    | Descrição |
|-------------------------|---------------------------|-----------|
| `enabled`               | `False`                   | Ativa o uso do RAG no pipeline ou MCP server. |
| `embedding_model`       | `"models/gemini-embedding-001"` | Modelo usado para gerar embeddings. |
| `embedding_dimension`   | `768`                     | Dimensão dos vetores retornados. |
| `enable_cache`          | `True`                    | Persiste vetores em `cache/embeddings/`. |
| `export_embeddings`     | `False`                   | Gera um arquivo Parquet com todos os chunks indexados. |
| `embedding_export_path` | `artifacts/embeddings/newsletter_chunks.parquet` | Caminho padrão do Parquet exportado (respeita caminhos relativos). |
| `vector_store_type`     | `"simple"`               | Usa `SimpleVectorStore` (in-memory + persistência local). |
| `chunk_size` / `chunk_overlap` | `1800` / `360`     | Tamanho e overlap dos trechos gerados pelo splitter. |
| `top_k` / `min_similarity`     | `5` / `0.65`        | Ajustes padrão para consultas semânticas. |

Definição completa: `src/egregora/rag/config.py`.

### Via `egregora.toml`

Habilite a seção `[rag]` no arquivo de configuração:

```toml
[rag]
enabled = true
embedding_model = "models/gemini-embedding-001"
embedding_dimension = 768
# Exporta embeddings em Parquet para publicar em artefatos
export_embeddings = true
embedding_export_path = "artifacts/embeddings/newsletter_chunks.parquet"
```

Qualquer campo omitido usa os defaults acima. Quando `enabled = true`, o módulo
passa a ser carregado pelo MCP server automaticamente.

### Via Python

```python
from pathlib import Path
from egregora.rag import NewsletterRAG
from egregora.rag.config import RAGConfig

config = RAGConfig(enabled=True, embedding_dimension=768)
rag = NewsletterRAG(
    newsletters_dir=Path("data/newsletters"),
    cache_dir=Path("cache"),
    config=config,
)
rag.update_index(force_rebuild=True)
results = rag.search("automações discutidas", top_k=3)
```

---

## 💾 Cache e Fallback

- Os vetores ficam em `cache/embeddings/` juntamente com metadados do modelo.
- `CachedGeminiEmbedding` grava cada embedding identificado por hash, evitando
  custos repetidos de API.
- Se a API não estiver disponível, o fallback interno usa hashing determinístico
  para produzir vetores estáveis, garantindo que o MCP server continue
  respondendo mesmo offline.

---

## 📦 Exportação e Artefatos

- Com `export_embeddings = true`, cada execução de `update_index()` escreve um
  Parquet em `embedding_export_path` contendo, por chunk, o texto, metadados e o
  vetor (como coluna de listas). O arquivo é sobrescrito em toda atualização.
- O caminho aceita valores relativos; por padrão salvamos em
  `artifacts/embeddings/newsletter_chunks.parquet`, facilitando o upload como
  artefato de GitHub Actions.
- Em workflows CI/CD, basta adicionar um passo de upload, por exemplo:

  ```yaml
  - name: Publicar embeddings
    uses: actions/upload-artifact@v4
    with:
      name: newsletter-embeddings
      path: artifacts/embeddings/newsletter_chunks.parquet
  ```

- Para enviar ao Internet Archive, reutilize o mesmo arquivo exportado; apenas
  certifique-se de executar o workflow com a chave apropriada e evite expor
  dados sensíveis no Parquet.

---

## 🔍 Consultas e Integração

- `NewsletterRAG.search(...)` retorna `NodeWithScore`, contendo o texto do chunk,
  a similaridade e metadados (data, seção) prontos para formatação.
- O MCP server expõe as ferramentas `search_newsletters`, `list_newsletters` e
  `get_newsletter`, reutilizando o índice carregado uma única vez por execução.
  

---

## ✅ Boas Práticas

- Execute `update_index(force_rebuild=True)` sempre que uma grande quantidade de
  newsletters for adicionada de uma vez.
- Mantenha a variável `GOOGLE_API_KEY` configurada para obter embeddings reais;
  sem ela o fallback funciona, mas os resultados são menos precisos.
- Utilize `cache_dir` dedicado em ambientes com múltiplos usuários para evitar
  conflitos de permissões.

---

## 🚀 Próximos Passos Sugeridos

1. Adicionar testes automatizados para `CachedGeminiEmbedding` e o pipeline de
   indexação.
2. Documentar benchmarks comparando o fallback determinístico com embeddings
   reais.
3. Permitir escolha dinâmica de `vector_store_type` via CLI/TOML quando outras
   opções (ex.: Chroma) forem necessárias.

Manter esta página alinhada com o código evita confusão sobre flags antigas e
reforça que a stack atual gira em torno do Gemini + LlamaIndex, com fallback
confiável para ambientes offline.
