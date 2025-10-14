from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb
from llama_index.core import VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.vector_stores.types import VectorStore
from llama_index.vector_stores.chroma import ChromaVectorStore

from .config import RAGConfig
from .embeddings import CachedGeminiEmbedding

if TYPE_CHECKING:
    from llama_index.core.schema import NodeWithScore

logger = logging.getLogger(__name__)


def _create_vector_store(db_path: Path, embed_model: BaseEmbedding) -> ChromaVectorStore:
    """Create or load a ChromaDB vector store."""
    db = chromadb.PersistentClient(path=str(db_path))
    chroma_collection = db.get_or_create_collection(
        name="egregora_rag_store",
        embedding_function=embed_model,  # type: ignore[arg-type]
    )
    return ChromaVectorStore(chroma_collection=chroma_collection)


def _load_index(vector_store: VectorStore, embed_model: BaseEmbedding) -> VectorStoreIndex:
    """Load the VectorStoreIndex from a vector store."""
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )


class PostRAG:
    """Handles RAG operations for posts."""

    def __init__(self, posts_dir: Path, config: RAGConfig):
        self.posts_dir = posts_dir
        self.config = config

    def search(self, query: str) -> list[NodeWithScore]:
        """Search for relevant posts."""
        embed_model = CachedGeminiEmbedding(
            model_name=self.config.embedding_model,
            dimension=self.config.embedding_dimension,
            cache_dir=self.config.cache_dir,
        )
        vector_store = _create_vector_store(self.config.persist_dir, embed_model)
        index = _load_index(vector_store, embed_model)

        retriever = index.as_retriever(similarity_top_k=self.config.top_k)
        return retriever.retrieve(query)
