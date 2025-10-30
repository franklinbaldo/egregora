import ibis
from pandas.testing import assert_frame_equal

from egregora.anonymizer import anonymize_table


def test_anonymize_table():
    data = {
        "author": ["John Doe", "Jane Smith", "John Doe"],
        "message": [
            "Hello Jane!",
            "Hi John! How are you?",
            "I'm good, thanks!",
        ],
    }
    table = ibis.memtable(data)

    anonymized_table = anonymize_table(table)

    expected_data = {
        "author": ["957cf4d6", "a54556c4", "957cf4d6"],
        "message": [
            "Hello Jane!",
            "Hi John! How are you?",
            "I'm good, thanks!",
        ],
    }
    expected_table = ibis.memtable(expected_data)

    # Convert to pandas for comparison
    result_pd = anonymized_table.execute().reset_index(drop=True)
    expected_pd = expected_table.execute().reset_index(drop=True)
    assert_frame_equal(result_pd, expected_pd)


def test_anonymize_table_with_mentions():
    data = {
        "author": ["John Doe"],
        "message": ["Hello \u2068Jane Smith\u2069! How are you?"],
    }
    table = ibis.memtable(data)

    anonymized_table = anonymize_table(table)

    expected_data = {
        "author": ["957cf4d6"],
        "message": ["Hello a54556c4! How are you?"],
    }
    expected_table = ibis.memtable(expected_data)

    # Convert to pandas for comparison
    result_pd = anonymized_table.execute().reset_index(drop=True)
    expected_pd = expected_table.execute().reset_index(drop=True)
    assert_frame_equal(result_pd, expected_pd)
