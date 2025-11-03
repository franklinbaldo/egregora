import pytest
from pathlib import Path
from src.egregora.ingestion.parser import parse_export
from tests.helpers.io import read_parquet
from tests.helpers.assert_parquet import assert_parquet_equal
from zoneinfo import ZoneInfo

@pytest.mark.golden
def test_ingest_preserves_source_fidelity(whatsapp_export_data):
    # Given
    export, con = whatsapp_export_data
    expected_path = Path('tests/fixtures/connectors/case1/stage1.raw.expected.parquet')

    # When
    messages_table = parse_export(export, timezone=None)
    df = messages_table.to_pandas()

    # Then
    expected_df = read_parquet(expected_path)

    # Sort by timestamp to ensure order is the same
    df = df.sort_values(by=['timestamp', 'author', 'message']).reset_index(drop=True)
    expected_df = expected_df.sort_values(by=['timestamp', 'author', 'message']).reset_index(drop=True)

    assert_parquet_equal(df, expected_df)


@pytest.mark.golden
def test_alias_resolution_is_stable(whatsapp_export_data, tmp_path):
    # Given
    export, con = whatsapp_export_data
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile_content = """---
uuid: 2b200d1a-454d-570a-9136-1616c27b0c34
alias: Test User
---
This is a test user profile.
"""
    (profiles_dir / "test_user.md").write_text(profile_content)

    expected_path = Path('tests/fixtures/identity/case1/stage3.identity.expected.parquet')

    # When
    messages_table = parse_export(export, timezone=None, profiles_dir=profiles_dir)
    df = messages_table.to_pandas()

    # Then
    expected_df = read_parquet(expected_path)

    # Sort by timestamp to ensure order is the same
    df = df.sort_values(by=['timestamp', 'author', 'message']).reset_index(drop=True)
    expected_df = expected_df.sort_values(by=['timestamp', 'author', 'message']).reset_index(drop=True)

    assert_parquet_equal(df, expected_df)


@pytest.mark.golden
def test_normalization_is_deterministic(whatsapp_export_data):
    # Given
    export, con = whatsapp_export_data
    expected_path = Path('tests/fixtures/parsing/case1/stage2.norm.expected.parquet')

    # When
    messages_table = parse_export(export, timezone=ZoneInfo("America/New_York"))
    df = messages_table.to_pandas()

    # Then
    expected_df = read_parquet(expected_path)

    # Sort by timestamp to ensure order is the same
    df = df.sort_values(by=['timestamp', 'author', 'message']).reset_index(drop=True)
    expected_df = expected_df.sort_values(by=['timestamp', 'author', 'message']).reset_index(drop=True)

    assert_parquet_equal(df, expected_df)
