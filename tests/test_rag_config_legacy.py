"""Regression tests for legacy RAG configuration flags."""

from __future__ import annotations

from pathlib import Path

import tomllib

import pytest
from pydantic import ValidationError

from egregora.config import PipelineConfig
from egregora.mcp_server.config import MCPServerConfig
from egregora.rag.config import RAGConfig, sanitize_rag_config_payload


def test_sanitize_rag_config_payload_strips_legacy_key() -> None:
    payload = {"enabled": True, "use_gemini_embeddings": False}
    assert sanitize_rag_config_payload(payload) == {"enabled": True}


def test_pipeline_config_accepts_legacy_flag() -> None:
    config = PipelineConfig(rag={"enabled": True, "use_gemini_embeddings": False})
    assert config.rag.enabled is True


def test_pipeline_config_from_toml_accepts_legacy_flag(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[rag]
enabled = true
use_gemini_embeddings = false
""".strip(),
        encoding="utf-8",
    )

    config = PipelineConfig.from_toml(config_path)
    assert config.rag.enabled is True


def test_mcp_server_config_accepts_legacy_flag() -> None:
    config = MCPServerConfig(rag={"enabled": True, "use_gemini_embeddings": True})
    assert config.rag.enabled is True


def test_mcp_server_config_from_path_accepts_legacy_flag(tmp_path: Path) -> None:
    config_path = tmp_path / "mcp.toml"
    config_path.write_text(
        """
[rag]
enabled = true
use_gemini_embeddings = true
""".strip(),
        encoding="utf-8",
    )

    config = MCPServerConfig.from_path(config_path)
    assert config.rag.enabled is True
    with config_path.open("rb") as fh:
        # Sanity check to ensure file contains the legacy key for future regressions.
        data = tomllib.load(fh)
    assert data["rag"]["use_gemini_embeddings"] is True


def test_rag_config_rejects_invalid_similarity() -> None:
    with pytest.raises(ValidationError) as exc:
        RAGConfig(min_similarity=1.2)

    assert "min_similarity must be between 0 and 1" in str(exc.value)


def test_rag_config_validates_chunk_overlap() -> None:
    with pytest.raises(ValidationError) as exc:
        RAGConfig(chunk_size=100, chunk_overlap=100)

    assert "chunk_overlap must be smaller than chunk_size" in str(exc.value)


def test_rag_config_rejects_zero_top_k() -> None:
    with pytest.raises(ValidationError) as exc:
        RAGConfig(top_k=0)

    assert "top_k must be greater than zero" in str(exc.value)
