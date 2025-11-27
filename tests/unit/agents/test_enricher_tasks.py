from __future__ import annotations

import ibis
import pytest

from egregora.agents import enricher


@pytest.mark.parametrize("limit", [0, -1])
def test_extract_url_candidates_short_circuits_when_limit_not_positive(monkeypatch, limit: int):
    """URL extraction should avoid scanning tables when no enrichments are allowed."""

    def _fail_iter(*_args, **_kwargs):
        raise AssertionError("_iter_table_batches should not be called when limit <= 0")

    monkeypatch.setattr(enricher, "_iter_table_batches", _fail_iter)

    empty_table = ibis.memtable([], schema=ibis.schema({"text": "string"}))

    assert enricher._extract_url_candidates(empty_table, limit) == []
