import pytest
from pathlib import Path
import duckdb
import ibis
from src.egregora.ingestion.parser import parse_export
from src.egregora.orchestration.pipeline import discover_chat_file
from src.egregora.core.models import WhatsAppExport
from datetime import datetime
from src.egregora.core.types import GroupSlug
from tests.helpers.io import read_parquet
from tests.helpers.assert_parquet import assert_parquet_equal

@pytest.mark.golden
def test_ingest_preserves_source_fidelity(tmp_path):
    # Given
    zip_path = Path('tests/Conversa do WhatsApp com Teste.zip')
    expected_path = Path('tests/fixtures/connectors/case1/stage1.raw.expected.parquet')

    # Set up a duckdb connection
    db_path = tmp_path / "test.db"
    con = duckdb.connect(database=str(db_path), read_only=False)
    ibis.set_backend(ibis.duckdb.connect(str(db_path)))

    # When
    group_name, chat_file = discover_chat_file(zip_path)
    export = WhatsAppExport(
        zip_path=zip_path,
        group_name=group_name,
        group_slug=GroupSlug(group_name.lower().replace(" ", "-")),
        export_date=datetime.now().date(),
        chat_file=chat_file,
        media_files=[],
    )

    messages_table = parse_export(export, timezone=None)
    df = messages_table.to_pandas()

    # Then
    expected_df = read_parquet(expected_path)

    # Sort by timestamp to ensure order is the same
    df = df.sort_values(by=['timestamp', 'author', 'message']).reset_index(drop=True)
    expected_df = expected_df.sort_values(by=['timestamp', 'author', 'message']).reset_index(drop=True)

    assert_parquet_equal(df, expected_df)
