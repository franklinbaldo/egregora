# RFC: Egregora v3 Data Model - Documents & Feeds

**Status:** Proposed
**Context:** Egregora v3 Re-architecture
**Date:** 2025-11-28
**Updated:** 2025-11-28 (Pivot: Semantic Identity & ContentLibrary)

## 1. Contexto e Objetivo

No v3, Egregora passa a adotar o protocolo **Atom** como modelo conceitual único para entrada e saída de dados. Isso elimina a distinção arbitrária entre "mensagens de chat", "posts de blog" e "arquivos", tratando tudo como entradas em um feed.

*   **Input:** Adapters convertem qualquer fonte (Chat, RSS, API Judicial) em `Feed` + `Entry`.
*   **Processamento:** O núcleo cognitivo processa esses `Entry`.
*   **Output:** O Egregora produz `Documents`.

Este RFC define o tipo `Document` e a estratégia de Output Feeds. O objetivo é garantir que:
1.  Exista um **único tipo de saída** (simplificação).
2.  O sistema seja **Atom-compliant**, facilitando a integração com leitores e ferramentas externas.
3.  A publicação seja agnóstica ao formato final (MkDocs, JSON API, Hugo, etc.).

## 2. Princípio de Simetria

A arquitetura v3 segue um fluxo linear e simétrico:

> **Input Feed → Processing → Output Feed**

1.  Egregora ingere feeds externos → normaliza para `Feed` + `Entry`.
2.  Egregora "pensa" e gera artefatos (posts, notas, planos) → cria objetos `Document`.
3.  Esses `Documents` são agregados em feeds de saída (ex: `egregora:documents`).

**Axioma:** Tudo que entra é Atom; tudo que sai é Atom (enriquecido).

## 3. Modelo de Dados

### 3.1. Base Atom (Core Domain)

O v3 define modelos Pydantic puros espelhando a especificação Atom (RFC 4287) e Atom Threading (RFC 4685), sem prefixos de legado.

```python
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class Link(BaseModel):
    href: str
    rel: str | None = None        # ex: "alternate", "enclosure", "self", "in-reply-to"
    type: str | None = None       # ex: "text/html", "image/jpeg"
    hreflang: str | None = None
    title: str | None = None
    length: int | None = None

class Author(BaseModel):
    name: str
    email: str | None = None
    uri: str | None = None

class Category(BaseModel):
    term: str                     # A tag ou categoria
    scheme: str | None = None     # URI do esquema de taxonomia
    label: str | None = None      # Label legível

class Source(BaseModel):
    id: str | None = None
    title: str | None = None
    updated: datetime | None = None
    links: list[Link] = Field(default_factory=list)

class InReplyTo(BaseModel):
    """Atom Threading Extension (RFC 4685)"""
    ref: str                      # ID da entry pai
    href: str | None = None       # Link para a entry pai
    type: str | None = None

class Entry(BaseModel):
    id: str                       # URI, UUID ou Slug Único
    title: str
    updated: datetime
    published: datetime | None = None

    links: list[Link] = Field(default_factory=list)
    authors: list[Author] = Field(default_factory=list)
    contributors: list[Author] = Field(default_factory=list)
    categories: list[Category] = Field(default_factory=list)

    summary: str | None = None    # Texto curto / Teaser
    content: str | None = None    # Corpo principal (geralmente Markdown/HTML)
    content_type: str | None = None # ex: "text/markdown"

    source: Source | None = None

    # Suporte a Threading (RFC 4685)
    in_reply_to: InReplyTo | None = None

    # Extensões públicas do padrão Atom (ex: Media RSS)
    extensions: dict[str, Any] = Field(default_factory=dict)

    # Metadados internos do sistema (não serializados em Atom público)
    internal_metadata: dict[str, Any] = Field(default_factory=dict)
```

### 3.2. Document: A Unidade de Saída

`Document` é a especialização de `Entry` gerada pelo Egregora. Ele carrega semântica específica do domínio da aplicação.

```python
from enum import Enum

class DocumentType(str, Enum):
    RECAP = "recap"      # Resumos de janelas de tempo
    NOTE = "note"        # Notas atômicas ou anotações de contexto
    PLAN = "plan"        # Planejamento de agentes
    POST = "post"        # Artigos completos para publicação
    MEDIA = "media"      # Metadados de mídia (o binário fica em links[rel=enclosure])
    ENRICHMENT = "enrichment" # Dados enriquecidos (sidecar) de outro item

class DocumentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class Document(Entry):
    """
    Representa um artefato gerado pelo Egregora.
    Herda de Entry para garantir compatibilidade com Atom.
    """
    doc_type: DocumentType
    status: DocumentStatus = DocumentStatus.DRAFT

    # Flag para indicar se deve ser indexado no RAG
    searchable: bool = True

    # Sugestão de caminho para OutputAdapters baseados em arquivo (MkDocs/Hugo)
    # Ex: "posts/2025/meu-artigo"
    url_path: str | None = None
```

## 4. Feeds de Saída (`documents_to_feed`)

Para manter a simetria, o output final de um ciclo de execução não é uma lista solta de arquivos, mas um objeto `Feed`.

```python
class Feed(BaseModel):
    id: str
    title: str
    updated: datetime
    entries: list[Entry] = Field(default_factory=list)
    # ... outros campos Atom (authors, links, etc.)

def documents_to_feed(
    docs: list[Document],
    feed_id: str,
    title: str,
    *,
    authors: list[Author] | None = None,
) -> Feed:
    """Agrega documentos em um Feed Atom válido."""
    # Lógica:
    # 1. Calcula updated = max(doc.updated) dos documentos
    # 2. Define entradas
    # 3. Garante invariantes de feed
    ...
```

## 5. Invariantes

### 5.1. Entry / Document
*   **Identidade Semântica ("Slug is King"):** Para tipos públicos (Post, Media), o `id` DEVE ser um slug legível e estável (ex: `2025-01-01-feliz-ano-novo`).
*   **UUIDs:** Usados apenas para tipos que exigem privacidade ou opacidade (ex: Author IDs, Internal Logs).
*   **Title:** Não vazio.
*   **Updated:** Obrigatório (UTC).
*   **Content Rule:** Deve ter `content` OU pelo menos um `link`.

### 5.2. Document Específico
*   **Type:** `doc_type` obrigatório.
*   **Status:** `status` obrigatório (default DRAFT).

## 6. Interações

### 6.1. Input Adapters
Ignorantes sobre `Document`. Eles produzem apenas `Feed` contendo `Entry`.
**Importante:** Entries de input (raw) geralmente têm `searchable=False` implícito para o sistema de RAG (ver seção 10).

### 6.2. Output Adapters
Assinatura da porta:
```python
class OutputSink(Protocol):
    def publish(self, feed: Feed) -> None: ...
```

## 7. Estratégia de TDD

1.  **Core Types:** Testar instanciação e validação de `Entry` e `Document`.
2.  **Feed Generation:** Testar `documents_to_feed` com listas variadas.
3.  **Threading:** Testar a relação pai/filho usando `in_reply_to`.

## 8. Organização e Persistência (ContentLibrary)

Abandonamos o modelo complexo de "Service Discovery" (AtomPub) em favor de um padrão de **Content Library** com injeção de dependência direta.

O `ContentLibrary` atua como uma fachada para os repositórios tipados do sistema.

```python
class ContentLibrary(BaseModel):
    # Repositórios tipados e explícitos
    posts: DocumentRepository
    media: DocumentRepository
    journal: DocumentRepository
    profiles: DocumentRepository

    # Metadata sobre o library (ex: configs globais)
    settings: dict[str, Any] = Field(default_factory=dict)
```

**Uso:**
O Agente ou Pipeline recebe `ContentLibrary` injetado e acessa diretamente:
```python
# Simples, direto, tipado
library.posts.save(doc)
```

## 9. Anotações e Threading (RFC 4685)

Anotações (comentários do agente sobre mensagens, notas de contexto) são tratadas nativamente usando a **Atom Threading Extension**.

### 9.1. Estrutura
Uma anotação é simplesmente um `Document` com `doc_type=NOTE` (ou `ANNOTATION`) que possui o campo `in_reply_to` preenchido.

```python
annotation = Document(
    id="note-123",
    doc_type=DocumentType.NOTE,
    content="Esta mensagem contradiz o que foi dito ontem.",
    in_reply_to=InReplyTo(ref="msg-original-id")
)
```

### 9.2. Linearização para LLM
Quando o sistema prepara o contexto (prompt) para a LLM:
1.  Ele carrega o Feed de entrada.
2.  Ele carrega o Feed de anotações/memória relevante.
3.  Ele realiza um "join" em memória: A anotação é inserida **imediatamente após** o Entry ao qual ela se refere (`in_reply_to.ref == entry.id`).

Isso garante que a LLM leia:
> *[User A]*: O céu é verde.
> *[Agente Note]*: (Falso. Em 2024-01-01 User A disse que era azul).

Sem precisar de estruturas de dados complexas no prompt, apenas a ordenação correta do Feed final.

## 10. Estratégia de Memória e RAG

Para evitar poluição da memória ("garbage in, garbage out"), definimos políticas claras de indexação baseadas nos tipos Atom:

### 10.1. Input Entries (Raw Data)
*   **Padrão:** Não indexados no RAG.
*   **Motivo:** Mensagens de chat bruto, logs judiciais não processados contêm muito ruído. O agente deve processá-los na janela de contexto atual, não recuperá-los via vetor.

### 10.2. Output Documents (Processed Data)
*   **Padrão:** Indexados no RAG (`searchable=True`).
*   **Motivo:** Posts, recaps e notas representam "pensamento cristalizado" e conhecimento de alta qualidade.

### 10.3. Workflow de Recuperação
1.  Agente faz uma query.
2.  RAG busca apenas em Collections marcadas como `index_in_rag=True` (ex: "posts", "journal", "enrichments").
3.  O resultado são `Documents` (Atom Entries), que são inseridos no contexto.

## 11. Enrichment (Padrão Sidecar)

Enrichment (ex: descrever uma imagem, sumarizar uma URL externa) não deve mutar o `Entry` original de input (preservando a integridade da fonte).

Usamos o padrão **Sidecar Document**:

1.  **Input:** `Entry(id="msg-1", content="Veja isso: http://...")`
2.  **Processo:** Agente Enricher lê a URL.
3.  **Output:** Cria um `Document(id="enrich-1", doc_type=ENRICHMENT)`.
    *   Este documento contém o resumo da URL.
    *   Possui `in_reply_to` (ou link `rel="related"`) apontando para `msg-1`.
    *   Possui `searchable=True` (vai para o RAG).

**Visualização:**
No prompt do Writer, o sistema apresenta:
> *Mensagem Original:* "Veja isso: http://..."
> *[Enrichment]*: "Resumo da URL: Artigo sobre IA..."

Isso mantém o dado original puro e o dado enriquecido acessível e indexável.
