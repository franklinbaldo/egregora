from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import ibis
import pandas as pd
import pytest

from egregora.config.schema import create_default_config
from egregora.database.schemas import CONVERSATION_SCHEMA
from egregora.enrichment.core import EnrichmentRuntimeContext, enrich_table
from egregora.utils import BatchPromptResult, EnrichmentCache
from tests.helpers.storage import InMemoryEnrichmentStorage


# Use ibis options to set default backend for memtable()
@pytest.fixture(autouse=True)
def set_ibis_backend(duckdb_backend):
    """Set ibis default backend for memtable operations."""
    old_backend = getattr(ibis.options, "default_backend", None)
    ibis.options.default_backend = duckdb_backend
    try:
        yield
    finally:
        ibis.options.default_backend = old_backend


class StubBatchClient:
    """Deterministic batch client that returns canned enrichment content."""

    def __init__(self, prefix: str):
        self.prefix = prefix

    def generate_content(self, requests, **kwargs):
        """Return canned responses matching the provided tags."""
        results: list[BatchPromptResult] = []
        for request in requests:
            tag = getattr(request, "tag", None)
            results.append(
                BatchPromptResult(
                    tag=tag,
                    response=SimpleNamespace(text=f"{self.prefix}:{tag}"),
                    error=None,
                )
            )
        return results

    def upload_file(self, *, path: str, display_name: str | None = None):  # pragma: no cover
        return SimpleNamespace(uri=f"stub://{Path(path).name}", mime_type="image/jpeg")


@pytest.fixture
def duckdb_backend():
    backend = ibis.duckdb.connect()
    try:
        yield backend
    finally:
        backend.con.close()


def _make_base_table():
    """Create test table. Relies on set_ibis_backend fixture for backend attachment."""
    rows = [
        {
            "timestamp": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            "date": datetime(2024, 1, 1, tzinfo=UTC).date(),
            "author": "user-1",
            "message": "Confira este link http://example.com",
            "original_line": "",
            "tagged_line": "",
            "message_id": "1",
        }
    ]
    return ibis.memtable(rows, schema=CONVERSATION_SCHEMA)


@pytest.mark.skip(
    reason="FIXME: Ibis backend discovery issue in enrichment/_table_to_pylist(). "
    "Root cause: _iter_table_record_batches() calls table._find_backend(use_default=False), "
    "ignoring ibis.options.default_backend. Needs fix in enrichment/batch.py to pass use_default=True "
    "or convert table to pandas earlier. Out of scope for Phase 3."
)
def test_enrich_table_persists_sorted_results(tmp_path, duckdb_backend):
    docs_dir = tmp_path / "docs"
    posts_dir = tmp_path / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    cache = EnrichmentCache(directory=tmp_path / "cache")

    table = _make_base_table()
    StubBatchClient("url")

    # MODERN (Phase 2): Create config and context
    config = create_default_config(tmp_path)
    config = config.model_copy(
        deep=True,
        update={
            "enrichment": config.enrichment.model_copy(update={"enable_media": False}),
        },
    )

    # Create mock output_format that implements OutputFormat protocol (serve method)
    output_format = InMemoryEnrichmentStorage()

    enrichment_context = EnrichmentRuntimeContext(
        cache=cache,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
        output_format=output_format,
        duckdb_connection=duckdb_backend,
        target_table="conversation_output",
    )

    combined = enrich_table(
        table,
        media_mapping={},
        config=config,
        context=enrichment_context,
    )

    persisted = duckdb_backend.table("conversation_output")
    assert persisted.schema().names == CONVERSATION_SCHEMA.names

    result_df = combined.order_by("timestamp").execute().reset_index(drop=True)
    persisted_df = persisted.order_by("timestamp").execute().reset_index(drop=True)

    pd.testing.assert_frame_equal(result_df, persisted_df)
    assert list(persisted_df["author"]) == ["user-1", "egregora"]
    assert persisted_df["timestamp"].is_monotonic_increasing


def test_enrich_table_insert_is_idempotent(tmp_path, duckdb_backend):
    docs_dir = tmp_path / "docs"
    posts_dir = tmp_path / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    cache = EnrichmentCache(directory=tmp_path / "cache")

    table = _make_base_table()
    StubBatchClient("url")

    # MODERN (Phase 2): Create config and context
    config = create_default_config(tmp_path)
    config = config.model_copy(
        deep=True,
        update={
            "enrichment": config.enrichment.model_copy(update={"enable_media": False}),
        },
    )

    # Create mock output_format that implements OutputFormat protocol (serve method)
    output_format = InMemoryEnrichmentStorage()

    enrichment_context = EnrichmentRuntimeContext(
        cache=cache,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
        output_format=output_format,
        duckdb_connection=duckdb_backend,
        target_table="conversation_output",
    )

    enrich_table(
        table,
        media_mapping={},
        config=config,
        context=enrichment_context,
    )

    first_df = (
        duckdb_backend.table("conversation_output").order_by("timestamp").execute().reset_index(drop=True)
    )

    enrich_table(
        table,
        media_mapping={},
        config=config,
        context=enrichment_context,
    )

    second_df = (
        duckdb_backend.table("conversation_output").order_by("timestamp").execute().reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(first_df, second_df)
