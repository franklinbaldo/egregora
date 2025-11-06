from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_ai.models.test import TestModel

from egregora.agents.writer.writer_agent import write_posts_with_pydantic_agent
from tests.utils.mock_batch_client import create_mock_batch_client

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def writer_dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    site_dir = tmp_path / "site" / "docs"
    posts_dir = site_dir / "posts"
    profiles_dir = site_dir / "profiles"
    rag_dir = site_dir / "rag"
    posts_dir.mkdir(parents=True)
    profiles_dir.mkdir()
    rag_dir.mkdir()
    return posts_dir, profiles_dir, rag_dir


def test_write_posts_with_test_model(writer_dirs: tuple[Path, Path, Path]) -> None:
    posts_dir, profiles_dir, rag_dir = writer_dirs
    batch_client = create_mock_batch_client()

    prompt = 'You reviewed an empty conversation. Respond with JSON {"summary": "No posts", "notes": "N/A"}.'

    saved_posts, saved_profiles = write_posts_with_pydantic_agent(
        prompt=prompt,
        model_name="models/gemini-flash-latest",
        period_date="2025-01-01",
        output_dir=posts_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        client=batch_client,
        embedding_model="models/gemini-embedding-001",
        embedding_output_dimensionality=3072,
        retrieval_mode="exact",
        retrieval_nprobe=None,
        retrieval_overfetch=None,
        annotations_store=None,
        agent_model=TestModel(call_tools=[], custom_output_text='{"summary": "No posts", "notes": "N/A"}'),
        register_tools=False,
    )

    assert saved_posts == []
    assert saved_profiles == []
