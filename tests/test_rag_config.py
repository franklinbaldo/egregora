from pathlib import Path

import pytest
from pydantic import ValidationError

from egregora.rag.config import RAGConfig

TOP_K = 10
MIN_SIMILARITY = 0.5


def test_rag_config_accepts_supported_fields(tmp_path: Path) -> None:
    config = RAGConfig(
        enabled=True,
        top_k="10",
        min_similarity="0.5",
        exclude_recent_days="3",
        max_context_chars="2048",
        max_keywords="4",
        keyword_stop_words=["Alpha", "Beta", ""],
        classifier_max_llm_calls="30",
        classifier_token_budget="4000",
        chunk_size="2048",
        chunk_overlap="256",
        embedding_model="custom/embedding",
        embedding_dimension="1536",
        enable_cache=False,
        cache_dir=str(tmp_path / "cache"),
        export_embeddings=True,
        embedding_export_path=str(tmp_path / "embeddings.parquet"),
        vector_store_type="chroma",
        persist_dir=str(tmp_path / "vector_store"),
        collection_name="custom-posts",
    )

    assert config.top_k == TOP_K
    assert config.min_similarity == MIN_SIMILARITY
    assert config.keyword_stop_words == ("alpha", "beta")
    assert config.cache_dir == tmp_path / "cache"
    assert config.embedding_export_path == tmp_path / "embeddings.parquet"
    assert config.persist_dir == tmp_path / "vector_store"


def test_rag_config_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RAGConfig(use_gemini_embeddings=True)


def test_rag_config_validates_overlap_bounds() -> None:
    with pytest.raises(ValidationError):
        RAGConfig(chunk_size=256, chunk_overlap=512)
