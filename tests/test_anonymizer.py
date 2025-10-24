
import polars as pl
from polars.testing import assert_frame_equal

from egregora.anonymizer import anonymize_dataframe


def test_anonymize_dataframe():
    data = {
        "author": ["John Doe", "Jane Smith", "John Doe"],
        "message": [
            "Hello Jane!",
            "Hi John! How are you?",
            "I'm good, thanks!",
        ],
    }
    df = pl.DataFrame(data)

    anonymized_df = anonymize_dataframe(df)

    expected_data = {
        "author": ["957cf4d6", "a54556c4", "957cf4d6"],
        "message": [
            "Hello Jane!",
            "Hi John! How are you?",
            "I'm good, thanks!",
        ],
    }
    expected_df = pl.DataFrame(expected_data)

    assert_frame_equal(anonymized_df, expected_df)

def test_anonymize_dataframe_with_mentions():
    data = {
        "author": ["John Doe"],
        "message": [f"Hello \u2068Jane Smith\u2069! How are you?"],
    }
    df = pl.DataFrame(data)

    anonymized_df = anonymize_dataframe(df)

    expected_data = {
        "author": ["957cf4d6"],
        "message": ["Hello a54556c4! How are you?"],
    }
    expected_df = pl.DataFrame(expected_data)

    assert_frame_equal(anonymized_df, expected_df)
