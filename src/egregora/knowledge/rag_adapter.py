from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import ibis
from ibis.expr.types import Table
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.vector_stores.lancedb import LanceDBVectorStore

if TYPE_CHECKING:
    from pathlib import Path

    from egregora.config.settings import EgregoraConfig
    from egregora.data_primitives import Document

# Constant from old implementation for deduplication
DEDUP_MAX_RANK = 2


class LlamaIndexRagAdapter:
    """Adapter for LlamaIndex RAG with LanceDB backend."""

    def __init__(self, config: EgregoraConfig, lancedb_path: Path):
        """Initialize the adapter with LanceDB and Gemini models."""
        self._config = config
        lancedb_path.mkdir(parents=True, exist_ok=True)
        self._lancedb_uri = str(lancedb_path)

        # Initialize LlamaIndex components
        self._embed_model = GeminiEmbedding(model_name=config.models.embedding)
        self._vector_store = LanceDBVectorStore(uri=self._lancedb_uri, table_name="vectors")
        self._storage_context = StorageContext.from_defaults(vector_store=self._vector_store)

        # Create or load the index from the vector store
        self._index = VectorStoreIndex.from_documents(
            [],  # Start with empty list; we insert nodes manually
            storage_context=self._storage_context,
            embed_model=self._embed_model,
        )

    def ingest_documents(self, documents: Iterable[Document]):
        """Convert Egregora Documents to LlamaIndex Nodes and ingest them."""
        nodes = []
        for doc in documents:
            if not isinstance(doc.content, str) or not doc.content.strip():
                continue

            metadata = {
                "document_id": doc.document_id,
                "slug": doc.slug,
                "document_type": doc.type.value,
                "created_at": doc.created_at.isoformat(),
                "parent_id": doc.parent_id,
                "source_window": doc.source_window,
            }
            for key, value in doc.metadata.items():
                if key in metadata:
                    continue
                if isinstance(value, (str, int, float, bool, type(None))):
                    metadata[key] = value
                elif isinstance(value, (datetime, date)):
                    metadata[key] = value.isoformat()
                else:
                    metadata[key] = str(value)

            node = TextNode(
                text=doc.content,
                metadata=metadata,
                id_=doc.document_id,
            )
            nodes.append(node)

        if nodes:
            self._index.insert_nodes(nodes)

    def _execute_query(
        self,
        query_text: str,
        top_k: int,
        min_similarity_threshold: float,
        filters: MetadataFilters | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a query against the LlamaIndex index and return results as dicts."""
        retriever = self._index.as_retriever(
            similarity_top_k=top_k,
            vector_store_kwargs={"similarity_cutoff": min_similarity_threshold},
            filters=filters,
        )
        results = retriever.retrieve(query_text)

        output_records = []
        for res in results:
            record = res.node.metadata.copy()
            record["similarity"] = res.score
            record["content"] = res.node.get_content()
            output_records.append(record)
        return output_records

    def query_similar_posts(
        self,
        table: Table,
        top_k: int = 5,
        deduplicate: bool = True,
    ) -> Table:
        """Find similar previous blog posts using LlamaIndex."""
        query_text = table.execute().to_csv(sep="|", index=False)
        rag_settings = self._config.rag

        # In LlamaIndex, top_k is applied before the similarity threshold.
        # To mimic the old behavior, we fetch more results and then filter.
        # We also fetch more to have enough data for deduplication.
        fetch_k = (top_k * 3) if deduplicate else top_k

        results_list = self._execute_query(
            query_text=query_text,
            top_k=fetch_k,
            min_similarity_threshold=rag_settings.min_similarity_threshold,
        )

        if not results_list:
            return ibis.memtable([])

        results_table = ibis.memtable(results_list)

        if deduplicate:
            window = ibis.window(group_by="slug", order_by=ibis.desc("similarity"))
            results_table = (
                results_table.order_by(ibis.desc("similarity"))
                .mutate(_rank=ibis.row_number().over(window))
                .filter(lambda t: t._rank < DEDUP_MAX_RANK)
                .drop("_rank")
                .order_by(ibis.desc("similarity"))
                .limit(top_k)
            )

        return results_table

    def query_media(
        self,
        query: str,
        media_types: list[str] | None = None,
        top_k: int = 5,
        min_similarity_threshold: float = 0.7,
        deduplicate: bool = True,
    ) -> Table:
        """Search for relevant media using LlamaIndex."""
        filters = MetadataFilters(filters=[ExactMatchFilter(key="document_type", value="enrichment_media")])

        fetch_k = (top_k * 3) if deduplicate else top_k

        results_list = self._execute_query(
            query_text=query,
            top_k=fetch_k,
            min_similarity_threshold=min_similarity_threshold,
            filters=filters,
        )

        if not results_list:
            return ibis.memtable([])

        results_table = ibis.memtable(results_list)

        if deduplicate:
            # Media enrichments might not have a unique slug, use parent_id
            window = ibis.window(group_by="parent_id", order_by=ibis.desc("similarity"))
            results_table = (
                results_table.order_by(ibis.desc("similarity"))
                .mutate(_rank=ibis.row_number().over(window))
                .filter(lambda t: t._rank < DEDUP_MAX_RANK)
                .drop("_rank")
                .order_by(ibis.desc("similarity"))
                .limit(top_k)
            )

        return results_table
