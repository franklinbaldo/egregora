"""LlamaIndex-powered retrieval over the newsletter archive."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, List

from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.schema import NodeWithScore
from llama_index.core.vector_stores import SimpleVectorStore

from .config import RAGConfig
from .embeddings import CachedGeminiEmbedding


@dataclass(slots=True)
class IndexStats:
    """Simple statistics about the current vector index."""

    total_newsletters: int
    total_chunks: int
    persist_dir: Path
    vector_store: str


class NewsletterRAG:
    """Manage the lifecycle of a LlamaIndex vector store for newsletters."""

    def __init__(
        self,
        *,
        newsletters_dir: Path,
        config: RAGConfig | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.newsletters_dir = Path(newsletters_dir).expanduser()
        self.newsletters_dir.mkdir(parents=True, exist_ok=True)

        base_config = copy.deepcopy(config) if config else RAGConfig()

        if cache_dir is not None:
            cache_dir = Path(cache_dir).expanduser()
            cache_dir.mkdir(parents=True, exist_ok=True)
            base_config.persist_dir = cache_dir / "vector_store"
            if base_config.enable_cache:
                base_config.cache_dir = cache_dir / "embeddings"

        if base_config.enable_cache:
            base_config.cache_dir = base_config.cache_dir.expanduser()
            base_config.cache_dir.mkdir(parents=True, exist_ok=True)

        base_config.persist_dir = base_config.persist_dir.expanduser()
        base_config.persist_dir.mkdir(parents=True, exist_ok=True)

        self.config = base_config

        self._embedding = CachedGeminiEmbedding(
            model_name=self.config.embedding_model,
            dimension=self.config.embedding_dimension,
            cache_dir=self.config.cache_dir if self.config.enable_cache else None,
        )

        self._chroma_client: Any = None
        self._chroma_collection: Any = None
        self._vector_store: Any = None
        self._storage_context: StorageContext | None = None
        self._index: VectorStoreIndex | None = None

        self._init_vector_store()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------
    def _init_vector_store(self) -> None:
        store_type = self.config.vector_store_type.lower()
        if store_type == "chroma":
            try:
                import chromadb
                from llama_index.vector_stores.chroma import ChromaVectorStore
            except ModuleNotFoundError as exc:  # pragma: no cover - chromadb optional
                raise RuntimeError(
                    "Dependência 'chromadb' não encontrada. Instale 'chromadb' para usar o vector store Chroma."
                ) from exc

            self._chroma_client = chromadb.PersistentClient(path=str(self.config.persist_dir))
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name=self.config.collection_name
            )
            self._vector_store = ChromaVectorStore(chroma_collection=self._chroma_collection)
        elif store_type == "simple":
            self._vector_store = SimpleVectorStore()
        else:  # pragma: no cover - defensive branch
            raise ValueError(
                f"Vector store '{self.config.vector_store_type}' não suportado nesta versão."
            )

        self._storage_context = StorageContext.from_defaults(vector_store=self._vector_store)

    def _build_empty_index(self) -> VectorStoreIndex:
        assert self._storage_context is not None
        self._index = VectorStoreIndex(
            [],
            storage_context=self._storage_context,
            embed_model=self._embedding,
        )
        return self._index

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_index(self) -> VectorStoreIndex:
        """Load an existing index or create a new one lazily."""

        return self.load_or_create_index()

    def load_or_create_index(self) -> VectorStoreIndex:
        if self._index is not None:
            return self._index

        try:
            assert self._vector_store is not None
            assert self._storage_context is not None
            self._index = VectorStoreIndex.from_vector_store(
                vector_store=self._vector_store,
                storage_context=self._storage_context,
                embed_model=self._embedding,
            )
        except Exception:  # pragma: no cover - falls back to empty index
            self._index = self._build_empty_index()

        return self._index

    def update_index(self, *, force_rebuild: bool = False) -> dict[str, int]:
        """Recreate the vector index from the Markdown newsletters."""

        documents = self._load_newsletter_documents()

        if force_rebuild:
            self._clear_collection()
            index = self._build_empty_index()
        else:
            index = self.load_or_create_index()
            for doc in documents:
                try:
                    index.delete_ref_doc(doc.doc_id, raise_error=False)  # type: ignore[call-arg]
                except TypeError:
                    # Older llama-index versions do not accept the keyword argument
                    try:
                        index.delete_ref_doc(doc.doc_id)  # type: ignore[call-arg]
                    except Exception:
                        continue
                except Exception:
                    continue

        parser = TokenTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )

        nodes = parser.get_nodes_from_documents(documents)
        if nodes:
            index.insert_nodes(nodes)

        return {
            "newsletters_count": len(documents),
            "chunks_count": len(nodes),
        }

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        min_similarity: float | None = None,
        exclude_recent_days: int | None = None,
    ) -> List[NodeWithScore]:
        """Execute a semantic similarity search over the indexed chunks."""

        if not query.strip():
            return []

        index = self.load_or_create_index()

        retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=top_k or self.config.top_k,
        )

        nodes = retriever.retrieve(query)

        exclude_days = (
            exclude_recent_days
            if exclude_recent_days is not None
            else self.config.exclude_recent_days
        )
        if exclude_days > 0:
            cutoff = date.today() - timedelta(days=exclude_days)
            nodes = self._filter_recent_nodes(nodes, cutoff)

        threshold = min_similarity if min_similarity is not None else self.config.min_similarity
        if threshold > 0:
            nodes = [node for node in nodes if node.score is None or node.score >= threshold]

        return nodes

    def get_stats(self) -> IndexStats:
        index = self.load_or_create_index()

        documents = index.docstore.docs.values()
        unique_files = set()
        for node in documents:
            metadata = getattr(node, "metadata", {})
            if isinstance(metadata, dict):
                path = metadata.get("file_path")
                if path:
                    unique_files.add(path)

        return IndexStats(
            total_newsletters=len(unique_files),
            total_chunks=len(documents),
            persist_dir=self.config.persist_dir,
            vector_store=self.config.vector_store_type,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _clear_collection(self) -> None:
        if self.config.vector_store_type.lower() == "chroma" and self._chroma_collection is not None:
            self._chroma_collection.delete()
            self._chroma_collection = None
            self._chroma_client = None
        self._index = None
        self._init_vector_store()

    def _load_newsletter_documents(self) -> List[Document]:
        documents: list[Document] = []
        for path in sorted(self.newsletters_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            metadata = {
                "file_path": str(path),
                "file_name": path.name,
            }
            extracted = self._extract_date(path)
            if extracted:
                metadata["date"] = extracted.isoformat()

            doc_id = f"newsletter::{path.stem}"
            documents.append(
                Document(
                    text=text,
                    doc_id=doc_id,
                    metadata=metadata,
                )
            )
        return documents

    def _extract_date(self, path: Path) -> date | None:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
        if not match:
            return None
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            return None

    def _filter_recent_nodes(
        self, nodes: List[NodeWithScore], cutoff: date
    ) -> List[NodeWithScore]:
        filtered: list[NodeWithScore] = []
        for node_with_score in nodes:
            metadata = getattr(node_with_score.node, "metadata", {})
            raw_date = metadata.get("date") if isinstance(metadata, dict) else None
            if not raw_date:
                filtered.append(node_with_score)
                continue
            try:
                node_date = date.fromisoformat(str(raw_date))
            except ValueError:
                filtered.append(node_with_score)
                continue
            if node_date < cutoff:
                filtered.append(node_with_score)
        return filtered


__all__ = ["NewsletterRAG", "IndexStats"]

