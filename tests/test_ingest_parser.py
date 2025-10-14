from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from egregora.ingest.anonymizer import Anonymizer
from egregora.ingest.main import ingest_zip as ingest_zip_function
from egregora.ingest.parser import (
    load_export_from_zip,
    parse_exports_lazy,
    parse_zip,
)

DATA_DIR = Path("tests/data/zips")
SAMPLE_ZIP = DATA_DIR / "Conversa do WhatsApp com Teste.zip"


def test_parse_zip_includes_enrichment_columns() -> None:
    frame = parse_zip(SAMPLE_ZIP)

    assert {"timestamp", "author", "anon_author", "message", "enriched_summary"}.issubset(
        set(frame.columns)
    )
    assert frame.with_columns((pl.col("author") == pl.col("anon_author")).alias("same")).select(
        pl.col("same").all()
    ).item(), "anon_author should default to original author before anonymization"


def test_parse_exports_lazy_collects_to_same_frame() -> None:
    export = load_export_from_zip(SAMPLE_ZIP)
    eager = parse_zip(SAMPLE_ZIP)
    lazy = parse_exports_lazy([export])

    collected = lazy.collect()
    assert collected.equals(eager)


def test_ingest_zip_function_matches_parser() -> None:
    frame = ingest_zip_function(SAMPLE_ZIP)
    baseline = parse_zip(SAMPLE_ZIP)
    assert frame.equals(baseline)


def test_anonymizer_ibis_memtable_roundtrip() -> None:
    pytest.importorskip("ibis")

    df = pl.DataFrame({"author": ["João Silva", "+55 11 98888-7777"]})
    memtable = Anonymizer.to_ibis_memtable(df, target_column="anon_author")

    materialized = memtable.op().data.to_frame()
    assert "anon_author" in materialized.columns
    assert materialized.loc[0, "anon_author"].startswith("Member-")
    assert materialized.loc[1, "anon_author"].startswith("Member-")
    assert materialized.loc[0, "author"] == "João Silva"
