from datetime import UTC, datetime

import ibis

from egregora_v3.core.types import Entry, Source
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository

UTC = UTC


def test_get_entries_by_source_uses_raw_sql_path_for_duckdb(tmp_path):
    """
    Verifies that the DuckDB repository uses the raw SQL path for JSON extraction,
    avoiding BinderExceptions common with Ibis JSON chained extraction.
    """
    db_path = tmp_path / "test.duckdb"
    con = ibis.duckdb.connect(str(db_path))
    repo = DuckDBDocumentRepository(con)
    repo.initialize()

    source_id = "test-source-123"
    entry = Entry(id="e1", title="Test Entry", updated=datetime.now(UTC), source=Source(id=source_id))
    repo.save_entry(entry)

    # This call triggers the logic in get_entries_by_source
    # If the Ibis path were used with this version of DuckDB/Ibis, it might raise BinderException
    # But we expect success via the raw SQL path.
    entries = repo.get_entries_by_source(source_id)

    assert len(entries) == 1
    assert entries[0].id == "e1"
    assert entries[0].source.id == source_id
