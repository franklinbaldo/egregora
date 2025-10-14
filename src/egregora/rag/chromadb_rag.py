"""ChromaDB-based RAG implementation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb

from .config import RAGConfig
from .embeddings import CachedGeminiEmbedding
from .indexer import list_markdown_files, split_into_chunks

if TYPE_CHECKING:
    from chromadb.api.types import QueryResult

logger = logging.getLogger(__name__)


class ChromadbRAG:
    """Handles RAG operations for posts using ChromaDB directly."""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.embed_model = CachedGeminiEmbedding(
            model_name=self.config.embedding_model,
            dimension=self.config.embedding_dimension,
            cache_dir=self.config.cache_dir,
        )
        self.client = chromadb.PersistentClient(path=str(self.config.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=self.config.collection_name,
        )

    def index_files(self, files_dir: Path):
        """Index all markdown files in a directory."""
        files = list_markdown_files(files_dir)
        if not files:
            logger.info("No markdown files found to index in %s", files_dir)
            return

        logger.info("Indexing %d markdown files from %s", len(files), files_dir)
        for file_path in files:
            self.index_file(file_path)

    def index_file(self, file_path: Path):
        """Index a single markdown file."""
        logger.info("Indexing %s", file_path)
        text = file_path.read_text(encoding="utf-8")
        chunks = split_into_chunks(
            text,
            chunk_chars=self.config.chunk_size,
            overlap_chars=self.config.chunk_overlap,
        )

        if not chunks:
            return

        documents = [chunk[1] for chunk in chunks]
        embeddings = self.embed_model(documents)
        metadatas = [
            {"source": str(file_path), "title": chunk[0] or ""} for chunk in chunks
        ]
        ids = [f"{file_path}:{i}" for i in range(len(chunks))]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, query: str) -> QueryResult:
        """Search for relevant posts."""
        query_embedding = self.embed_model([query])[0]
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=self.config.top_k,
        )
        return results
