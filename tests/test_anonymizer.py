import ibis

from egregora.privacy.anonymizer import anonymize_table


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

    # Verify anonymization
    result = anonymized_table.execute()
    assert list(result["author"]) == ["957cf4d6", "a54556c4", "957cf4d6"]
    assert list(result["message"]) == [
        "Hello Jane!",
        "Hi John! How are you?",
        "I'm good, thanks!",
    ]


def test_anonymize_table_with_mentions():
    data = {
        "author": ["John Doe"],
        "message": ["Hello \u2068Jane Smith\u2069! How are you?"],
    }
    table = ibis.memtable(data)

    anonymized_table = anonymize_table(table)

    # Verify anonymization with mentions
    result = anonymized_table.execute()
    assert list(result["author"]) == ["957cf4d6"]
    assert list(result["message"]) == ["Hello a54556c4! How are you?"]
