"""Tests for the CSVOutputSink."""

import csv
from datetime import datetime
from pathlib import Path

from egregora_v3.core.types import (
    Document,
    DocumentStatus,
    DocumentType,
    Feed,
    Entry,
)
from egregora_v3.infra.sinks.csv import CSVOutputSink


def test_csv_output_sink_publishes_correctly(tmp_path: Path):
    """Tests that CSVOutputSink correctly filters and writes published documents."""
    # 1. Setup
    csv_file = tmp_path / "output.csv"
    now = datetime.now()

    published_doc = Document(
        title="Published Post",
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
        updated=now,
        published=now,
        content="Hello world.",
    )
    draft_doc = Document(
        title="Draft Post",
        doc_type=DocumentType.POST,
        status=DocumentStatus.DRAFT,
        updated=now,
    )
    plain_entry = Entry(id="plain-entry", title="Just an Entry", updated=now)

    feed = Feed(
        id="test-feed",
        title="My Test Feed",
        updated=now,
        entries=[published_doc, draft_doc, plain_entry],
    )

    sink = CSVOutputSink(csv_file)

    # 2. Action
    sink.publish(feed)

    # 3. Assertions
    assert csv_file.exists()

    with csv_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == published_doc.id
    assert row["title"] == "Published Post"
    assert row["status"] == DocumentStatus.PUBLISHED.value
    assert row["doc_type"] == DocumentType.POST.value
    assert row["content"] == "Hello world."
