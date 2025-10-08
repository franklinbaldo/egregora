"""Smoke test for the simplified backlog processor."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from scripts.process_backlog import process_backlog


def test_process_backlog_generates_posts() -> None:
    base_dir = Path("tests/temp_output/backlog_smoke") / uuid4().hex
    shutil.rmtree(base_dir, ignore_errors=True)
    zip_dir = base_dir / "zips"
    output_dir = base_dir / "posts"
    zip_dir.mkdir(parents=True, exist_ok=True)

    sample_zip = Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")
    shutil.copy(sample_zip, zip_dir / sample_zip.name)

    summary = process_backlog(zip_dir, output_dir, force=True, verbose=False)

    assert summary.zip_count == 1
    assert summary.posts_generated >= 1
    assert summary.groups_processed >= 1
    assert output_dir.exists()
    assert any(output_dir.rglob("*.md"))

    shutil.rmtree(base_dir, ignore_errors=True)
