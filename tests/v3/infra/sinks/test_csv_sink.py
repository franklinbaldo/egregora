"""Tests for the CSVOutputSink."""

import csv
from datetime import datetime, UTC
from pathlib import Path

import pytest

from egregora_v3.core.types import (
    Author,
    Document,
    DocumentStatus,
    DocumentType,
    Feed,
)
from egregora_v3.infra.sinks.csv import CSVOutputSink


@pytest.fixture
def sample_feed() -> Feed:
    """Provides a sample Feed with DRAFT and PUBLISHED documents."""
    published_doc = Document(
        id="published-doc",
        title="Published Document",
        updated=datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
        content="This is a published document.",
        authors=[Author(name="Test Author")],
    )
    draft_doc = Document(
        id="draft-doc",
        title="Draft Document",
        updated=datetime(2023, 1, 2, 12, 0, 0, tzinfo=UTC),
        doc_type=DocumentType.NOTE,
        status=DocumentStatus.DRAFT,
        content="This is a draft document.",
    )
    return Feed(
        id="test-feed",
        title="Test Feed",
        updated=datetime.now(UTC),
        entries=[published_doc, draft_doc],
    )


def test_csv_sink_publishes_only_published_documents(
    tmp_path: Path, sample_feed: Feed
):
    """Verify that only PUBLISHED documents are written to the CSV."""
    # 1. Setup
    csv_path = tmp_path / "output.csv"
    sink = CSVOutputSink(csv_path)

    # 2. Action
    sink.publish(sample_feed)

    # 3. Verification
    assert csv_path.exists()

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["id"] == "published-doc"
    assert rows[0]["status"] == "published"
