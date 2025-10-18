"""Simplified DuckDB-based RAG pipeline with Ibis queries."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import duckdb
import numpy as np

try:  # pragma: no cover - optional dependency
    import ibis
    from ibis import duckdb as idb
except ModuleNotFoundError as exc:  # pragma: no cover - ibis is optional at runtime
    raise RuntimeError(
        "The 'ibis-framework[duckdb]' dependency is required to use the DuckDB RAG pipeline"
    ) from exc

try:  # pragma: no cover - optional dependency
    from google import generativeai as genai
except ModuleNotFoundError:  # pragma: no cover - allows offline usage
    genai = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


EmbedFn = Callable[[Sequence[str], str], np.ndarray]
GenerateFn = Callable[[str, Sequence[str]], str]


@dataclass(slots=True)
class DuckDBSimpleConfig:
    """Configuration for :class:`DuckDBSimpleRAG`."""

    embedding_model: str = "models/embedding-001"
    generation_model: str = "gemini-1.5-flash"
    embedding_dimension: int = 768
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 3
    db_path: str = ":memory:"


def split_documents(
    documents: Sequence[str], *, chunk_size: int = 500, overlap: int = 50
) -> list[str]:
    """Split documents into overlapping chunks.

    A simple character-based splitter with overlap is used to preserve context
    across chunk boundaries. The behaviour matches the reference implementation
    shared by the product requirements: short documents are returned as-is while
    longer texts are sliced into roughly ``chunk_size`` character pieces with an
    ``overlap`` of characters to avoid truncating sentences abruptly.
    """

    chunks: list[str] = []
    for doc in documents:
        text = doc.strip()
        if not text:
            continue
        if len(text) <= chunk_size:
            chunks.append(text)
            continue

        start = 0
        length = len(text)
        while start < length:
            end = min(start + chunk_size, length)
            chunk = text[start:end]
            if end < length:
                last_period = chunk.rfind(".")
                if last_period > chunk_size // 2:
                    chunk = chunk[: last_period + 1]
                    end = start + len(chunk)
            chunks.append(chunk.strip())
            if end >= length:
                break
            next_start = max(0, end - overlap)
            if next_start <= start:
                next_start = end
            start = next_start
    return chunks


class DuckDBSimpleRAG:
    """Minimal retrieval augmented generation built on DuckDB VSS.

    The implementation mirrors the "simplest RAG" blueprint requested in the
    requirements: Gemini embeddings feed a DuckDB table with HNSW indexing
    while Ibis coordinates ingestion and query execution. Optional fallbacks
    keep the class usable in offline or test environments.
    """

    def __init__(
        self,
        config: DuckDBSimpleConfig | None = None,
        *,
        embed_fn: EmbedFn | None = None,
        generate_fn: GenerateFn | None = None,
    ) -> None:
        self._config = config or DuckDBSimpleConfig()
        if self._config.embedding_dimension < 1:
            raise ValueError("embedding_dimension must be positive")
        if self._config.chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        if self._config.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be zero or positive")
        if self._config.top_k < 1:
            raise ValueError("top_k must be positive")

        self._embed_fn = embed_fn or self._default_embed
        self._generate_fn = generate_fn or self._default_generate

        self._con = idb.connect(database=self._config.db_path)
        self._duckdb = self._con.con
        self._initialise_database()

    def close(self) -> None:
        """Close any open connections."""

        try:
            self._con.disconnect()
        finally:
            self._duckdb.close()

    def __enter__(self) -> "DuckDBSimpleRAG":  # pragma: no cover - convenience
        return self

    def __exit__(self, *_exc) -> None:  # pragma: no cover - convenience
        self.close()

    # ------------------------------------------------------------------
    # Database helpers
    def _initialise_database(self) -> None:
        """Install VSS extension, create the docs table and index."""

        try:
            self._duckdb.execute("INSTALL vss;")
        except duckdb.ConversionException:  # pragma: no cover - already installed
            pass
        except duckdb.Error as exc:  # pragma: no cover - log but continue
            logger.debug("Unable to install DuckDB VSS extension", exc_info=exc)
        try:
            self._duckdb.execute("LOAD vss;")
        except duckdb.Error as exc:  # pragma: no cover - log but continue
            logger.debug("Unable to load DuckDB VSS extension", exc_info=exc)

        self._duckdb.execute(
            """
            CREATE TABLE IF NOT EXISTS docs (
                id INTEGER PRIMARY KEY,
                text VARCHAR,
                embedding DOUBLE[]
            );
            """
        )
        try:
            self._duckdb.execute(
                """
                CREATE INDEX IF NOT EXISTS docs_hnsw ON docs USING HNSW(embedding)
                WITH (metric = 'cosine');
                """
            )
        except duckdb.Error as exc:  # pragma: no cover - extension may be unavailable
            logger.debug("Unable to create HNSW index", exc_info=exc)

    def _allocate_ids(self, count: int) -> Iterable[int]:
        next_id = self._duckdb.execute("SELECT COALESCE(MAX(id) + 1, 0) FROM docs;").fetchone()[
            0
        ]
        for offset in range(count):
            yield int(next_id) + offset

    # ------------------------------------------------------------------
    # Public API
    def ingest(self, documents: Sequence[str]) -> None:
        """Split, embed and persist documents."""

        chunks = split_documents(
            documents,
            chunk_size=self._config.chunk_size,
            overlap=self._config.chunk_overlap,
        )
        if not chunks:
            return

        embeddings = self._embed_fn(chunks, "RETRIEVAL_DOCUMENT")
        if embeddings.shape[1] != self._config.embedding_dimension:
            raise ValueError(
                "Embedding function returned vectors with unexpected dimension"
            )

        ids = list(self._allocate_ids(len(chunks)))
        payload = [
            {"id": idx, "text": chunk, "embedding": vector.tolist()}
            for idx, chunk, vector in zip(ids, chunks, embeddings, strict=False)
        ]
        if not payload:
            return

        table = ibis.memtable(payload)
        self._con.insert("docs", table, overwrite=False)

    def retrieve(self, query: str, *, top_k: int | None = None) -> list[str]:
        """Return the most similar chunks to ``query``."""

        top_k = top_k or self._config.top_k
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_vector = self._embed_fn([query], "RETRIEVAL_QUERY")[0]
        array_literal = ", ".join(f"{value:.12f}" for value in query_vector.tolist())
        # DuckDB exposes ``list_inner_product`` for cosine similarity when vectors are
        # normalised. Ibis does not yet wrap this helper, so we emit a tiny SQL snippet
        # through ``Backend.sql`` to keep the retrieval logic declarative.
        sql = (
            "SELECT text FROM ("
            "SELECT text, list_inner_product(embedding, [" + array_literal + "]) AS similarity "
            "FROM docs"
            ") ORDER BY similarity DESC LIMIT "
            + str(top_k)
        )
        result = self._con.sql(sql).execute()
        if "text" not in result.columns:
            return []
        return [value for value in result["text"].tolist() if isinstance(value, str)]

    def generate(self, query: str, retrieved_docs: Sequence[str]) -> str:
        """Generate an answer using the retrieved context."""

        return self._generate_fn(query, retrieved_docs)

    # ------------------------------------------------------------------
    # Default LLM interactions
    def _default_embed(self, texts: Sequence[str], task_type: str) -> np.ndarray:
        vectors: list[np.ndarray]
        if genai is None:
            vectors = [self._fallback_vector(text) for text in texts]
        else:  # pragma: no cover - depends on external service
            try:
                response = genai.embed_content(
                    model=self._config.embedding_model,
                    contents=list(texts),
                    task_type=task_type,
                    output_dimensionality=self._config.embedding_dimension,
                )
                embeddings = getattr(response, "embeddings", None)
                if embeddings:
                    vectors = [np.asarray(item.values, dtype=float) for item in embeddings]
                else:
                    vectors = [self._fallback_vector(text) for text in texts]
            except Exception as exc:  # pragma: no cover - gracefully fall back
                logger.debug("Falling back to deterministic embeddings", exc_info=exc)
                vectors = [self._fallback_vector(text) for text in texts]

        if not vectors:
            return np.zeros((0, self._config.embedding_dimension), dtype=float)

        matrix = np.vstack([self._normalise_vector(vector) for vector in vectors])
        return matrix

    def _default_generate(self, query: str, retrieved_docs: Sequence[str]) -> str:
        context = "\n\n".join(doc.strip() for doc in retrieved_docs if doc.strip())
        if not context:
            context = "(nenhum contexto relevante encontrado)"
        prompt = (
            "Contexto:\n"
            f"{context}\n\n"
            f"Pergunta: {query}\n\n"
            "Responda apenas com base no contexto acima. Seja conciso."
        )
        if genai is None:  # pragma: no cover - offline behaviour
            return self._fallback_answer(query, retrieved_docs)
        try:  # pragma: no cover - depends on external service
            response = genai.generate_content(self._config.generation_model, prompt)
            text = getattr(response, "text", None)
            if text:
                return text.strip()
        except Exception as exc:  # pragma: no cover - gracefully fall back
            logger.debug("Falling back to local answer generation", exc_info=exc)
        return self._fallback_answer(query, retrieved_docs)

    # ------------------------------------------------------------------
    # Deterministic fallbacks for offline usage
    def _fallback_vector(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = np.frombuffer(digest, dtype=np.uint8).astype(float)
        if raw.size == 0:
            return np.zeros(self._config.embedding_dimension, dtype=float)
        repeated = np.resize(raw, self._config.embedding_dimension)
        return repeated.astype(float)

    def _normalise_vector(self, vector: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vector)
        if norm == 0:
            return np.zeros(self._config.embedding_dimension, dtype=float)
        return (vector / norm).astype(float)

    def _fallback_answer(self, query: str, retrieved_docs: Sequence[str]) -> str:
        summary = " ".join(doc.strip() for doc in retrieved_docs if doc.strip())
        if not summary:
            return f"Não encontrei contexto para responder: {query}"
        return f"Pergunta: {query}\nResposta com base no contexto: {summary}".strip()


__all__ = ["DuckDBSimpleRAG", "DuckDBSimpleConfig", "split_documents"]
