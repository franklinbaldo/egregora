"""Tests for the self-reflection input adapter."""

from __future__ import annotations

import json
from pathlib import Path

from egregora.input_adapters.self_reflection import SelfInputAdapter
from egregora.output_adapters import create_output_format


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
    output_format = create_output_format(tmp_path, format_type="mkdocs")
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Self Test")
    assert created

    posts_dir = tmp_path / "docs" / "posts"
    post_one = posts_dir / "2025-01-01-sample.md"
    post_two = posts_dir / "2025-01-02-second.md"
    _write_markdown(post_one, "Sample", "sample-post", "Body text 1")
    _write_markdown(post_two, "Second", "second-post", "Body text 2")

    table = adapter.parse(tmp_path, output_adapter=output_format)
    df = table.execute()

    assert set(df.columns) == set(table.schema().names)
    assert df.shape[0] == 2

    recorded_slugs = set(df["thread_id"].tolist())
    assert {"sample-post", "second-post"} == recorded_slugs
    assert all(text.strip() for text in df["text"].tolist())

    attrs_value = df.iloc[0]["attrs"]
    if isinstance(attrs_value, str):
        attrs_value = json.loads(attrs_value)
    assert "source_path" in attrs_value
    assert attrs_value["slug"]

    assert "Egregora" in adapter.content_summary
