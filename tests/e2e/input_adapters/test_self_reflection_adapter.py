"""Tests for the self-reflection input adapter."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from egregora.output_adapters import create_default_output_registry, create_output_sink

from egregora.data_primitives.document import DocumentType
from egregora.input_adapters.self_reflection import SelfInputAdapter

if TYPE_CHECKING:
    from pathlib import Path


def _write_markdown(path: Path, title: str, slug: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
title: {title}
slug: {slug}
date: 2025-01-01
authors:
  - anon-1234
summary: test summary
---

{body}
""",
        encoding="utf-8",
    )


def test_self_adapter_parses_existing_site(tmp_path: Path):
    adapter = SelfInputAdapter()
    registry = create_default_output_registry()
    output_format = create_output_sink(tmp_path, format_type="mkdocs", registry=registry)
    output_format.initialize(tmp_path)
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Self Test")
    assert created

    # Use the adapter's configured posts directory to match its expectations
    posts_dir = getattr(output_format, "posts_dir", tmp_path / "docs" / "posts")
    post_one = posts_dir / "2025-01-01-sample.md"
    post_two = posts_dir / "2025-01-02-second.md"
    _write_markdown(post_one, "Sample", "sample-post", "Body text 1")
    _write_markdown(post_two, "Second", "second-post", "Body text 2")

    # The adapter should now scan the filesystem itself
    table = adapter.parse(tmp_path, output_adapter=output_format, doc_type=DocumentType.POST)
    dataframe = table.execute()

    assert set(dataframe.columns) == set(table.schema().names)
    assert dataframe.shape[0] == 2

    recorded_slugs = set(dataframe["thread_id"].tolist())
    assert {"sample-post", "second-post"} == recorded_slugs
    assert all(text.strip() for text in dataframe["text"].tolist())

    attrs_value = dataframe.iloc[0]["attrs"]
    if isinstance(attrs_value, str):
        attrs_value = json.loads(attrs_value)
    assert "source_path" in attrs_value
    assert attrs_value["slug"]

    assert "Egregora" in adapter.content_summary
