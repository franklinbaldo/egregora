# Gemini Embeddings para RAG

## Visão geral

O sistema RAG do Egregora opera com dois modos complementares:

1. **TF-IDF clássico** (padrão) — rápido, sem custo de API e ideal para buscas por termos literais.
2. **Embeddings do Gemini** (opcional) — busca semântica avançada com suporte a sinônimos, variações linguísticas e contexto multimodal.

Ambos os modos compartilham o mesmo pipeline de indexação (`src/egregora/rag/`), permitindo alternar ou combinar estratégias conforme o cenário.

## Quando usar embeddings?

Use **TF-IDF** quando:

- Precisa buscar termos técnicos exatos ou abreviações específicas.
- Deseja zero custo de API e indexação instantânea.
- Executa consultas de diagnóstico ou com baixa ambiguidade.

Prefira **embeddings** quando:

- Busca conceitos amplos ("como configurar autenticação") ou perguntas abertas.
- Quer resultados robustos a sinônimos, variações e idiomas diferentes.
- Precisa correlacionar contextos entre newsletters, chats e materiais externos.
- Já utiliza o MCP server com clientes como Claude Desktop e quer respostas mais ricas.

## Como ativar

### Via CLI

```bash
uv run egregora --use-gemini-embeddings --embedding-dimension 768
```

Flags relevantes:

- `--use-gemini-embeddings`: ativa o fluxo semântico.
- `--embedding-dimension`: aceita `768`, `1536` ou `3072` (padrão: `768`).
- `--force-reindex`: recria o índice mesmo se o cache existir.

### Via código Python

```python
from pathlib import Path
from egregora.rag import NewsletterRAG, RAGConfig
from google import genai

client = genai.Client()
config = RAGConfig(use_gemini_embeddings=True, embedding_dimension=768)

rag = NewsletterRAG(
    newsletters_dir=Path("newsletters"),
    cache_dir=Path("cache"),
    config=config,
    gemini_client=client,
)

rag.load_index()  # usa cache se disponível
results = rag.search("como resolver problemas de conexão", top_k=5)
```

## Cache de embeddings

Os vetores calculados são armazenados em `cache/embeddings/` para evitar custos repetidos:

```
cache/embeddings/
├── index.json        # metadados (dimensão, versão, datas)
└── {hash}.npy        # vetores NumPy por documento
```

Use `--force-reindex` para reconstruir o índice ou limpe a pasta manualmente.

## Custos estimados

| Operação            | TF-IDF          | Embeddings Gemini                  |
|---------------------|-----------------|------------------------------------|
| Indexação inicial   | Instantânea     | ~5 minutos para 500 newsletters    |
| Custo de indexação  | $0              | ~US$0.025 (embeddings 768 dims)    |
| Custo de queries    | $0              | ~US$0.01/mês (100 buscas)          |
| Latência média      | <1 ms           | ~500 ms (inclui chamada à API)     |
| Qualidade           | Termos literais | Semântica, sinônimos, multilíngue  |

> Os valores são estimativas com base na tabela pública de preços do Gemini (`gemini-embedding-001`). Ajuste conforme o volume real.

## Boas práticas

- **Habilite o cache**: deixe `embedding_cache_enabled=True` para evitar custos recorrentes.
- **Escolha a dimensão adequada**: `768` equilibra custo e precisão; `3072` é reservado para casos críticos.
- **Combine filtros**: use `min_similarity` e `top_k` para ajustar o retorno em cada consulta.
- **Fallback automático**: se a API estiver indisponível, o RAG retorna ao TF-IDF.

## Troubleshooting

| Sintoma                                      | Possível causa                         | Ação sugerida                               |
|---------------------------------------------|----------------------------------------|---------------------------------------------|
| "Embeddings muito lentos"                  | Dimensão alta ou sem cache             | Reduza para 768 e confirme `cache/embeddings`|
| "Custo acima do esperado"                  | Reindexações frequentes                | Verifique se `--force-reindex` está desativado|
| "Resultados semânticos pouco relevantes"   | Poucos dados ou consultas muito curtas | Forneça contexto adicional ou aumente `top_k`|
| Erro `PermissionDenied` do Gemini           | API key sem acesso ao modelo           | Habilite `gemini-embedding-001` no console    |

## Próximos passos

- Documentar benchmarks comparando TF-IDF x embeddings.
- Adicionar testes automatizados cobrindo geração e cache de embeddings.
- Expandir o MCP server para permitir escolha dinâmica do modo de busca por tool.

*Última atualização: 2025-10-03*
