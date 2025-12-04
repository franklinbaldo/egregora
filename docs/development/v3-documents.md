# RFC: Egregora v3 Data Model - Documents & Feeds

**Status:** Proposed
**Context:** Egregora v3 Re-architecture
**Date:** 2025-11-28

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

O v3 define modelos Pydantic puros espelhando a especificação Atom (RFC 4287), sem prefixos de legado.

```python
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class Link(BaseModel):
    href: str
    rel: str | None = None        # ex: "alternate", "enclosure", "self"
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

class Entry(BaseModel):
    id: str                       # URI ou UUID único e estável
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

    # Sugestão de caminho para OutputAdapters baseados em arquivo (MkDocs/Hugo)
    # Ex: "posts/2025/meu-artigo"
    url_path: str | None = None
```

#### Notas de Implementação
1.  **Herança:** Como `Document` é um `Entry`, qualquer função de persistência ou indexação que aceite `Entry` aceita `Document`.
2.  **Conteúdo:** `content` deve ser preferencialmente texto (Markdown). Binários (imagens, PDFs gerados) devem ser referenciados via `links` com `rel="enclosure"`, mantendo o objeto `Document` leve.
3.  **Metadados:**
    *   `extensions`: Use para dados que fariam sentido em um feed RSS público (ex: coordenadas geo, licença).
    *   `internal_metadata`: Use para dados de controle do Egregora (ex: `tokens_used`, `model_version`, `source_window_id`).

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
    # ... outros opcionais
) -> Feed:
    """Agrega documentos em um Feed Atom válido."""
    # Lógica:
    # 1. Calcula updated = max(doc.updated) dos documentos
    # 2. Define entradas
    # 3. Garante invariantes de feed
    ...
```

**Uso:**
Isso permite que um `OutputAdapter` receba um `Feed` e decida como persistir:
*   **MkDocsAdapter:** Itera sobre `feed.entries`, olha `url_path` e escreve arquivos `.md`.
*   **APIAdapter:** Retorna o JSON do Feed diretamente.
*   **RSSAdapter:** Serializa o objeto para XML.

## 5. Invariantes

### 5.1. Entry / Document
*   **ID Estável:** O `id` deve ser não-vazio e, idealmente, determinístico (ex: UUIDv5 baseado no conteúdo ou slug + data) para permitir atualizações idempotentes.
*   **Title:** Não vazio.
*   **Updated:** Obrigatório (UTC).
*   **Content Rule:** Deve ter `content` OU pelo menos um `link` (ex: para documentos que são apenas referências a algo externo).

### 5.2. Document Específico
*   **Type:** `doc_type` obrigatório.
*   **Status:** `status` obrigatório (default DRAFT).

## 6. Interações

### 6.1. Input Adapters
Ignorantes sobre `Document`. Eles produzem apenas `Feed` contendo `Entry`.

### 6.2. Memory / RAG
A memória indexa `Entry`. Como `Document` é um `Entry`, ele é indexado nativamente, permitindo que o Egregora "lembre" do que ele mesmo escreveu no passado (self-reflection) sem código especial.

### 6.3. Output Adapters
Assinatura da porta:
```python
class OutputSink(Protocol):
    def publish(self, feed: Feed) -> None: ...
```
O adaptador recebe o feed completo. Ele pode filtrar (ex: publicar apenas status=PUBLISHED) e decidir o layout físico.

## 7. Estratégia de TDD

1.  **Core Types:** Testar instanciação e validação de `Entry` e `Document` (garantir campos obrigatórios).
2.  **Feed Generation:** Testar `documents_to_feed` com lista vazia (deve gerar feed válido com updated atual) e lista populada (updated = max(entries)).
3.  **Adapter Contract:** Criar um FakeAdapter que consome um Feed e verificar se ele acessa os campos corretos de `Document` (como `url_path`).
4.  **Roundtrip:** Testar Serialização/Deserialização Pydantic para garantir que nada se perde.
