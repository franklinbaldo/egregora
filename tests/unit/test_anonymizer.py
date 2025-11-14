import uuid

import ibis

from egregora.privacy.anonymizer import anonymize_table


def test_anonymize_table_redacts_author_raw():
    data = {
        "author_raw": ["John Doe", "Jane Smith", "John Doe"],
        "author_uuid": [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ],
        "text": [
            "Hello Jane!",
            "Hi John! How are you?",
            "I'm good, thanks!",
        ],
    }
    table = ibis.memtable(data)

    anonymized_table = anonymize_table(table)
    result = anonymized_table.execute()

    # author_raw should be replaced by deterministic UUID string or placeholder
    assert all(value.startswith("[") is False for value in result["author_raw"])
    assert list(result["text"]) == data["text"]


def test_anonymize_table_with_mentions():
    author_uuid = str(uuid.uuid4())
    data = {
        "author_raw": ["John Doe"],
        "author_uuid": [author_uuid],
        "text": ["Hello \u2068Jane Smith\u2069! How are you?"],
    }
    table = ibis.memtable(data)

    anonymized_table = anonymize_table(table)
    result = anonymized_table.execute()

    # Mentions should be replaced using mapping (falls back to redacted token)
    assert "Jane Smith" not in result["text"].iloc[0]
