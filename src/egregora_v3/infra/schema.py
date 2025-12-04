"""Ibis Schema definition for the Unified Document Store.

Matches the RFC 2025-11-28 specification.
"""

import ibis
import ibis.expr.datatypes as dt

# Unified Schema for the 'documents' table
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
    # Stored as JSON strings in DuckDB/Ibis usually, handled via Pydantic on app side
    # Ibis generic JSON support varies, using dt.json or dt.string depending on backend support.
    # DuckDB supports JSON type.
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

TABLE_NAME = "documents"
