import ibis
import pandas as pd
from pandas.testing import assert_frame_equal

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
    df = ibis.memtable(data)

    anonymized_df = anonymize_dataframe(df)

    expected_data = {
        "author": ["957cf4d6", "a54556c4", "957cf4d6"],
        "message": [
            "Hello Jane!",
            "Hi John! How are you?",
            "I'm good, thanks!",
        ],
    }
    expected_df = ibis.memtable(expected_data)

    # Convert to pandas for comparison
    result_pd = anonymized_df.execute().reset_index(drop=True)
    expected_pd = expected_df.execute().reset_index(drop=True)
    assert_frame_equal(result_pd, expected_pd)


def test_anonymize_dataframe_with_mentions():
    data = {
        "author": ["John Doe"],
        "message": ["Hello \u2068Jane Smith\u2069! How are you?"],
    }
    df = ibis.memtable(data)

    anonymized_df = anonymize_dataframe(df)

    expected_data = {
        "author": ["957cf4d6"],
        "message": ["Hello a54556c4! How are you?"],
    }
    expected_df = ibis.memtable(expected_data)

    # Convert to pandas for comparison
    result_pd = anonymized_df.execute().reset_index(drop=True)
    expected_pd = expected_df.execute().reset_index(drop=True)
    assert_frame_equal(result_pd, expected_pd)
