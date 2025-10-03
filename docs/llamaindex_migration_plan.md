# Plano de Migração para LlamaIndex

## 1. Contexto Atual

A implementação vigente do RAG da Egregora vive em `src/egregora/rag/` e foi construída
manualmente sobre vetores TF-IDF com suporte opcional a embeddings do Gemini. Os principais
componentes são:

- `core.py`: contém a classe `NewsletterRAG`, responsável por carregar, indexar e consultar
  as newsletters. Ele orquestra chunking, cálculo de TF-IDF, chamada opcional aos embeddings e
  persistência em JSON local.
- `indexer.py`: faz o pré-processamento de newsletters (chunking, extração de metadados) e
  expõe utilitários para a criação do índice.
- `search.py`: agrega funções para gerar vetores, calcular similaridade de cosseno e fazer
  tokenização básica. Também implementa parte do pipeline tradicional de ranking.
- `embedding_cache.py` e `embeddings.py`: lidam com cache local e chamadas ao Gemini,
  encapsulando o cálculo de embeddings quando a flag `RAGConfig.use_gemini_embeddings` está
  ativa.
- `query_gen.py`: gera consultas alternativas a partir das instruções do usuário.

Além disso, `src/egregora/config.py` define a dataclass `RAGConfig`, que controla todos os
parâmetros do subsistema atual (chunking textual, limites de similaridade, uso de MCP, etc.).
A integração com o servidor MCP ocorre em `src/egregora/mcp_server/tools.py`, que hoje instancia
`NewsletterRAG` diretamente e chama os métodos `update_index`, `search` e `get_index_stats`.

## 2. Objetivo da Migração

Substituir a implementação proprietária por uma arquitetura baseada no **LlamaIndex** que:

1. Centralize chunking, embeddings, armazenamento vetorial e retrieval em componentes mantidos
   pela comunidade.
2. Permita persistência em vector stores reais (Chroma, Qdrant, etc.).
3. Ofereça extensibilidade para pós-processamento, re-ranking e combinações híbridas.
4. Reduza o código próprio necessário para manter o RAG, mantendo ou melhorando a qualidade das
   respostas.

## 3. Arquitetura Proposta com LlamaIndex

### 3.1 Estrutura de Pastas

```
src/egregora/rag/
├── __init__.py
├── config.py            # Novo: configurações específicas da camada LlamaIndex
├── index.py             # Novo: classe NewsletterRAG reimplementada sobre LlamaIndex
├── embeddings.py        # Novo: wrapper para Gemini embeddings com cache opcional
├── postprocessors.py    # Novo: filtros (ex.: excluir newsletters recentes)
├── retrievers.py        # Opcional: ganchos para retrieval híbrido ou especializado
└── legacy/              # Código antigo mantido temporariamente durante a transição
    ├── core.py
    ├── indexer.py
    ├── search.py
    ├── embeddings.py
    └── embedding_cache.py
```

### 3.2 Dependências

Adicionar ao `pyproject.toml` e `requirements.txt`:

- `llama-index-core`
- `llama-index-embeddings-gemini`
- `llama-index-vector-stores-chroma` (ou adaptação para o vector store escolhido)
- driver do vector store (ex.: `chromadb`)

### 3.3 Componentes Principais

1. **Configuração (`config.py`)**: uma nova dataclass `RAGIndexConfig` contendo parâmetros de chunking,
   persistência do vector store, modelo de embeddings e opções de cache. Esta classe pode coexistir com
   a atual `RAGConfig`, que continuará servindo ao restante do pipeline.
2. **Embeddings (`embeddings.py`)**: classe `CachedGeminiEmbedding` derivada de `BaseEmbedding` do
   LlamaIndex, encapsulando chamada ao Gemini e implementando caching local similar ao atual
   `EmbeddingCache`.
3. **Index (`index.py`)**: nova `NewsletterRAG` que usa `VectorStoreIndex`, `StorageContext` e
   `TokenTextSplitter` do LlamaIndex. Responsabilidades:
   - Carregar ou recriar o índice persistido em um vector store.
   - Converter newsletters em `Document` com metadados (caminho, título, data).
   - Inserir/atualizar `Node`s no índice com chunking baseado em tokens.
   - Expor métodos `update_index`, `search`, `get_stats` alinhados com a API atual para minimizar
     alterações no restante do código.
4. **Pós-processamento (`postprocessors.py`)**: primeiro passo é portar o filtro de datas (excluir
   newsletters recentes) usando `BaseNodePostprocessor`. No futuro, incluir re-ranking por
   similaridade textual, filtros por newsletter específica, etc.
5. **Retrievers (`retrievers.py`, opcional)**: espaço para adicionar combinações híbridas (BM25 + vetor)
   ou heurísticas customizadas mantendo a interface do LlamaIndex.

## 4. Passos de Migração

### 4.1 Preparação

1. Criar uma branch dedicada (`feature/migrate-rag-llamaindex`).
2. Instalar as novas dependências e garantir que os pacotes atuais que se tornarem obsoletos (por
   exemplo, funções de TF-IDF) sejam marcados para remoção após a migração.
3. Esboçar testes de regressão cobrindo `NewsletterRAG.update_index`, `NewsletterRAG.search` e
   `NewsletterRAG.get_index_stats` usando fixtures de newsletters sintéticas em `tests/fixtures/`.

### 4.2 Implementação Incremental

1. **Configuração**
   - Criar `src/egregora/rag/config.py` com `RAGIndexConfig`.
   - Atualizar `src/egregora/config.py` para incluir o novo bloco de configuração ou para delegar
     atributos relevantes ao novo módulo.

2. **Camada de Embeddings**
   - Adicionar `CachedGeminiEmbedding` compatível com o LlamaIndex e portar (ou reusar) o cache já
     disponível em `embedding_cache.py`.
   - Ajustar o uso de `GOOGLE_API_KEY` e demais variáveis de ambiente existentes.

3. **Indexação**
   - Implementar `NewsletterRAG` em `index.py` usando `VectorStoreIndex` com `ChromaVectorStore`
     (ou a solução decidida).
   - Fornecer métodos `load_or_create_index`, `update_index(force_rebuild: bool)`, `search` e
     `get_stats` compatíveis com os nomes já consumidos pelo MCP.
   - Implementar utilitário para extrair data do nome do arquivo e anexar aos metadados do node.

4. **Integração com MCP e CLI**
   - Atualizar `src/egregora/mcp_server/tools.py` para importar a nova implementação e adaptar o
     consumo de `NodeWithScore` (incluindo preview de texto, caminho e data nas respostas).
   - Revisar scripts CLI que manipulem o RAG (ex.: `scripts/enrichment_rag.py` se existir) para usar a
     nova API.

5. **Migração de Dados**
   - Criar script em `scripts/migrate_rag_store.py` para reconstruir o índice a partir das newsletters
     existentes usando a nova `NewsletterRAG`. O script deve invalidar o JSON antigo e gerar o
     vector store persistido.
   - Incluir instruções no README para executar o script após atualizar o projeto.

6. **Convivência e Remoção do Código Antigo**
   - Mover `core.py`, `indexer.py`, `search.py` e arquivos auxiliares para `src/egregora/rag/legacy/`
     para permitir fallback durante a fase de testes.
   - Após validação, remover referências ao código legado e apagar o diretório `legacy`.

### 4.3 Testes

1. Criar `tests/rag/test_llamaindex_integration.py` com cenários que:
   - Indexam um conjunto pequeno de newsletters e validam a contagem de chunks.
   - Executam buscas e verificam metadados retornados, incluindo filtro por datas.
   - Garantem que o índice pode ser recriado após exclusão do diretório de persistência.
2. Opcional: manter testes de regressão comparando os primeiros resultados do RAG antigo e do novo
   para queries fixas, garantindo fidelidade semântica.

## 5. Atualizações de Documentação

1. Atualizar `docs/mcp-rag.md` e `README.md` com a nova arquitetura, instruções de configuração e
   dependências.
2. Criar `docs/migration-llamaindex.md` explicando:
   - Breaking changes (ex.: objetos `NodeWithScore` retornados na busca).
   - Passo a passo para reconstruir o índice.
   - Novas variáveis de ambiente (caso surjam).
3. Atualizar planos de testes (`TESTING_PLAN.md`) para incluir cenários com LlamaIndex.

## 6. Validação e Deploy

1. Rodar `pytest` e quaisquer comandos adicionais (`ruff`, `mypy`, etc.) garantindo que o pipeline
   atual permaneça estável.
2. Executar benchmarks simples de tempo de indexação e latência de consulta comparando implementações
   antiga e nova (scripts podem ser adicionados em `scripts/benchmarks/`).
3. Revisar o consumo do RAG em todo o projeto (ex.: `enrichment.py`, `pipeline.py`) para confirmar que
   a interface não quebrou.
4. Após validação, remover o diretório `rag/legacy/` e atualizar referências.

## 7. Roadmap Pós-Migração

- **Semantic chunking**: experimentar `SemanticSplitterNodeParser` para melhorar a coesão dos chunks.
- **Hybrid search**: combinar BM25 + vector search usando `QueryFusionRetriever` para queries mais
  longas.
- **Reranking**: integrar `SentenceTransformerRerank` ou similares para melhorar a qualidade dos
  resultados finais.
- **Observabilidade**: configurar logging e métricas (tempo de indexação, latência de query, número
  de nodes) para acompanhar a saúde do RAG em produção.

Este plano cobre o ciclo completo — da preparação das dependências até a validação final — e pode ser
executado em etapas incrementais, permitindo feature toggles e rollback caso necessário.
