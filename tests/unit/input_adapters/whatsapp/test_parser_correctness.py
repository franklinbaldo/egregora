import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from egregora.input_adapters.whatsapp.parsing import WhatsAppExport, parse_source

# Define the path to the fixture data
FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "whatsapp"
CHAT_FILE_PATH = FIXTURE_DIR / "_chat.txt"
GOLDEN_PARQUET_PATH = FIXTURE_DIR / "expected_output.parquet"


@pytest.fixture
def whatsapp_export_fixture(tmp_path: Path) -> WhatsAppExport:
    """Creates a mock WhatsApp export ZIP from the fixture file."""
    zip_path = tmp_path / "whatsapp.zip"
    chat_file_name = "_chat.txt"
    chat_content = CHAT_FILE_PATH.read_text()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(chat_file_name, chat_content)

    return WhatsAppExport(
        zip_path=zip_path,
        group_name="Test Group",
        group_slug="test-group",
        export_date=date(2022, 1, 1),
        chat_file=chat_file_name,
        media_files=[],
    )


def test_parse_source_correctness(whatsapp_export_fixture: WhatsAppExport):
    """
    Tests that the output of parse_source matches the expected golden file.

    If the golden file does not exist, it will be created, and the test
    will fail. This is the mechanism for generating a new golden file.
    """
    # 1. Run the parser
    result_table = parse_source(whatsapp_export_fixture, timezone="UTC")
    result_df = result_table.to_pandas()

    # Ibis adds timezone information, which might not be in the golden file.
    # Let's make sure the timestamp column is consistent.
    if "ts" in result_df.columns and pd.api.types.is_datetime64_any_dtype(result_df["ts"]):
        result_df["ts"] = pd.to_datetime(result_df["ts"]).dt.tz_localize(None)

    # 2. Check for the golden file
    if not GOLDEN_PARQUET_PATH.exists():
        # Golden file doesn't exist, so create it.
        result_df.to_parquet(GOLDEN_PARQUET_PATH, index=False)
        pytest.fail(
            f"Golden file did not exist. A new one has been created at:"
            f"\\n{GOLDEN_PARQUET_PATH}"
            f"\\nPlease review it and commit it to the repository."
        )

    # 3. Load the golden file and compare
    expected_df = pd.read_parquet(GOLDEN_PARQUET_PATH)

    # Ensure timestamp columns are comparable
    if "ts" in expected_df.columns and pd.api.types.is_datetime64_any_dtype(expected_df["ts"]):
        expected_df["ts"] = pd.to_datetime(expected_df["ts"]).dt.tz_localize(None)

    # ibis might create different types for columns, let's sort by columns to avoid ordering issues
    # and reset index to compare values
    result_df = result_df.sort_values(by="event_id").reset_index(drop=True)
    expected_df = expected_df.sort_values(by="event_id").reset_index(drop=True)

    # Reorder columns to match
    expected_df = expected_df[result_df.columns]

    assert_frame_equal(result_df, expected_df, check_dtype=False)
