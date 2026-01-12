"""Tests for the declarative WhatsApp parser."""

import pytest

from egregora.input_adapters.whatsapp.parsing import parse_source as declarative_parse_source
from egregora.input_adapters.whatsapp.parsing_legacy import parse_source as legacy_parse_source

# A sample WhatsApp export file content
SAMPLE_CHAT_CONTENT = """
1/1/24, 10:00 - Alice: Hi Bob!
This is a multi-line message.
1/1/24, 10:01 - Bob: Hey Alice! How are you?
1/1/24, 10:02 - Alice: I'm good, thanks!
"""


@pytest.fixture
def sample_whatsapp_export(tmp_path):
    """Creates a dummy WhatsApp export zip file for testing."""
    import zipfile
    from datetime import date

    from egregora.input_adapters.whatsapp.parsing import WhatsAppExport

    zip_path = tmp_path / "whatsapp.zip"
    chat_file_name = "_chat.txt"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(chat_file_name, SAMPLE_CHAT_CONTENT)

    return WhatsAppExport(
        zip_path=zip_path,
        group_name="Test Group",
        group_slug="test-group",
        export_date=date(2024, 1, 1),
        chat_file=chat_file_name,
        media_files=[],
    )


def test_declarative_parser_matches_legacy(sample_whatsapp_export):
    """
    Tests that the output of the new declarative parser is identical to the legacy parser.
    """
    # 1. Run the legacy parser on the sample_whatsapp_export.
    legacy_result = legacy_parse_source(sample_whatsapp_export)
    legacy_df = legacy_result.execute()

    # 2. Run the new declarative parser on the same export.
    declarative_result = declarative_parse_source(sample_whatsapp_export)
    declarative_df = declarative_result.execute()

    # 3. Assert that the resulting Ibis tables are identical.
    # For robust comparison, we'll use pandas testing utilities.
    import pandas as pd

    # Ensure columns are in the same order
    declarative_df = declarative_df[legacy_df.columns]

    pd.testing.assert_frame_equal(legacy_df, declarative_df, check_dtype=False)
