# RFC: Egregora v3 Architecture - Atom-Centric & Single-Table

**Status:** Approved for Implementation
**Context:** Egregora v3 Re-architecture
**Date:** 2025-11-28
**Core Principle:** "Data is the only state."

## 1. Visão Geral

A arquitetura v3 abandona a complexidade de tabelas relacionais e logs de execução (`runs`) em favor de um modelo de dados unificado baseado no padrão **Atom**.

*   **Input:** Adapters convertem fontes (Chat, RSS) em `Entries`.
*   **Storage:** Um único "Store" armazena tudo como `Documents` (que são `Entries` enriquecidos).
*   **Output:** Coleções de documentos são exportadas como Feeds.
*   **Estado:** O estado do pipeline é derivado exclusivamente dos dados existentes (High Water Mark).

## 2. Modelo de Dados (Atom-First)

Tudo no sistema é uma variação de um **Entry Atom**. Não existem mais tipos distintos para "Mensagem", "Post" ou "Mídia" no nível do banco de dados.

### 2.1. Unified Document Schema (Camada de Persistência)

O banco de dados (DuckDB) terá **apenas uma tabela**: `documents`.

```python
import ibis
import ibis.expr.datatypes as dt

UNIFIED_SCHEMA = ibis.schema({
    # Identidade e Organização (AtomPub semantics)
    "id": dt.string,              # UUID/URI determinístico
    "collection": dt.string,      # ex: "whatsapp-raw", "posts", "journal"
    "doc_type": dt.string,        # ex: "entry", "post", "note", "media"

    # Núcleo Atom (RFC 4287)
    "title": dt.string,
    "content": dt.string,         # Markdown/Texto principal
    "updated": dt.timestamp,      # Cursor temporal universal
    "published": dt.timestamp,
    "summary": dt.string,

    # Metadados Ricos (JSON)
    "authors": dt.json,           # Lista de autores
    "links": dt.json,             # Links (mídia, fontes, relacionados)
    "tags": dt.json,              # Categorias

    # Extensões e Controle Interno
    "extensions": dt.json,        # Dados "públicos" (geo, license, media-rss)
    "internal_metadata": dt.json, # Dados de sistema (tokens, model_version, source_ref)

    # Relacionamentos e Busca
    "parent_id": dt.string,       # Threading (RFC 4685 in-reply-to)
    "embedding": dt.Array(dt.float32), # Vetor para RAG
    "searchable": dt.boolean      # Se deve aparecer na busca do agente
})
```

### 2.2. Domínio (Python Types)

No código Python, usamos Pydantic para garantir a validade desses dados.

*   **`Entry`:** Modelo base (puro Atom).
*   **`Document`:** Subclasse de `Entry` com campos auxiliares (`doc_type`, `collection`, `searchable`).

## 3. Organização Lógica (AtomPub-style)

O sistema organiza os dados em **Workspaces** e **Collections**, eliminando a necessidade de o agente "adivinhar" caminhos de arquivo.

1.  **Service Catalog:** O agente consulta "quais coleções existem?".
2.  **Collections:**
    *   `"whatsapp-raw"`: Onde o adapter despeja mensagens (searchable=False).
    *   `"posts"`: Onde o agente cria blog posts (searchable=True).
    *   `"journal"`: Memória de longo prazo (searchable=True).
    *   `"media"`: Metadados de arquivos (o binário fica no disco, linkado via `rel="enclosure"`).

## 4. Resumability e Estado (No `runs` table)

**Decisão:** A tabela `runs` foi eliminada. O sistema é stateless.

Para continuar de onde parou (resume), o pipeline usa a estratégia **High Water Mark**:

1.  **Query:** `SELECT MAX(updated) FROM documents WHERE collection = 'whatsapp-raw' AND processed = True` (ou derivado de `source` nos posts de saída).
2.  **Filtro:** O input adapter lê tudo, mas o pipeline descarta qualquer item com `updated <= last_max`.

**Benefício:** Se você apagar os posts de saída, o sistema regenera tudo automaticamente. O estado é uma função direta dos dados presentes.

## 5. RAG e Memória

A indexação no RAG é controlada pela flag `searchable` no documento.

*   **Input Bruto (Chat):** `searchable=False`. O agente lê na janela de contexto da execução atual, mas não polui o índice global.
*   **Conhecimento Sintetizado (Posts/Notas):** `searchable=True`. O "conhecimento" do Egregora é formado apenas pelo que ele já processou e refinou.

Isso resolve o problema de "garbage in, garbage out" na memória vetorial.

## 6. Enrichment (Sidecar Pattern)

Enriquecimento (ex: descrever URL) não altera o documento original. Cria-se um novo documento na coleção `"enrichments"`:

*   `doc_type="enrichment"`
*   `parent_id="id-da-mensagem-original"`
*   `content="Resumo da URL..."`
*   `searchable=True`

No momento da leitura, o sistema faz um *join* lógico (via parent_id) e entrega o conteúdo original + enriquecimento para o LLM.

## 7. Implementação: Próximos Passos

1.  **Core (`src/egregora_v3/core/`):**
    *   Definir modelos Pydantic `Entry` e `Document`.
    *   Definir interfaces `DocumentRepository` e `VectorStore`.

2.  **Infra (`src/egregora_v3/infra/`):**
    *   Implementar `DuckDBRepository` gerenciando a **tabela única** `documents`.
    *   Garantir que `save(doc)` seja idempotente (upsert por ID).

3.  **Pipeline (`src/egregora_v3/pipeline/`):**
    *   Implementar lógica de Windowing baseada em `updated` timestamp.
    *   Implementar loop principal: `Input -> Filter(Resume) -> Window -> Agent -> Save`.

Esta arquitetura remove radicalmente a complexidade de gerenciamento de estado, tornando o v3 mais robusto, fácil de testar e preparado para qualquer tipo de dado (não só chat).
