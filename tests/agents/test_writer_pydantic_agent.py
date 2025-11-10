from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest
from pydantic_ai.models.test import TestModel

from egregora.agents.shared.rag import VectorStore
from egregora.agents.writer.agent import WriterRuntimeContext, write_posts_with_pydantic_agent
from egregora.config.loader import create_default_config
from tests.helpers.storage import InMemoryJournalStorage, InMemoryPostStorage, InMemoryProfileStorage
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

    # MODERN (Phase 2): Create config and context
    site_root = posts_dir.parent.parent  # Go up from docs/posts to site root
    config = create_default_config(site_root)
    config = config.model_copy(
        deep=True,
        update={
            "rag": config.rag.model_copy(update={"mode": "exact"}),
        },
    )

    # MODERN (Adapter Pattern): Use in-memory storage for testing
    posts_storage = InMemoryPostStorage()
    profiles_storage = InMemoryProfileStorage()
    journals_storage = InMemoryJournalStorage()
    rag_store = VectorStore(rag_dir / "chunks.parquet")

    context = WriterRuntimeContext(
        start_time=datetime(2025, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
        end_time=datetime(2025, 1, 1, 23, 59, tzinfo=ZoneInfo("UTC")),
        # Storage protocols (in-memory for testing)
        posts=posts_storage,
        profiles=profiles_storage,
        journals=journals_storage,
        # Pre-constructed stores
        rag_store=rag_store,
        annotations_store=None,
        # LLM client
        client=batch_client,
        # Prompt templates directory
        prompts_dir=None,
        # Deprecated (kept for backward compatibility)
        output_dir=posts_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        site_root=site_root,
    )

    # Note: TestModel doesn't create actual tool calls, so saved_posts will be empty
    # This test just verifies the agent runs without errors
    test_model = TestModel(call_tools=[], custom_output_text='{"summary": "No posts", "notes": "N/A"}')

    saved_posts, saved_profiles = write_posts_with_pydantic_agent(
        prompt=prompt,
        config=config,
        context=context,
        test_model=test_model,
    )

    assert saved_posts == []
    assert saved_profiles == []
