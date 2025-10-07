"""Regression tests for legacy RAG configuration flags."""

from __future__ import annotations

from pathlib import Path

import tomllib

from egregora.config import PipelineConfig
from egregora.mcp_server.config import MCPServerConfig
from egregora.rag.config import sanitize_rag_config_payload


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
