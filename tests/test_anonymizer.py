import uuid
from datetime import date, datetime

import polars as pl

from egregora.anonymizer import Anonymizer

ANON_SUFFIX_LENGTH = 4
UUID_FULL_LENGTH = 36
UUID_SHORT_LENGTH = 8


def test_normalize_phone_strips_non_digits() -> None:
    assert Anonymizer.normalize_phone("(11) 98765-4321") == "11987654321"


def test_anonymize_phone_is_deterministic() -> None:
    token_a = Anonymizer.anonymize_phone("+55 11 98765-4321")
    token_b = Anonymizer.anonymize_phone("5511987654321")

    assert token_a == token_b
    assert token_a.startswith("Member-")
    suffix = token_a.split("-")[1]
    assert len(suffix) == ANON_SUFFIX_LENGTH
    assert suffix.isupper()


def test_anonymize_nickname_uses_member_prefix() -> None:
    token_a = Anonymizer.anonymize_nickname(" João Silva ")
    token_b = Anonymizer.anonymize_nickname("joão silva")

    assert token_a == token_b
    assert token_a.startswith("Member-")


def test_anonymize_author_treats_short_numbers_as_nicknames() -> None:
    assert Anonymizer.anonymize_author("12345") == Anonymizer.anonymize_nickname("12345")


def test_get_uuid_variants_returns_human_identifier() -> None:
    variants = Anonymizer.get_uuid_variants("Maria")

    assert set(variants.keys()) == {"full", "short", "human"}
    assert variants["human"].startswith("Member-")
    assert len(variants["full"]) == UUID_FULL_LENGTH
    assert len(variants["short"]) == UUID_SHORT_LENGTH


def test_anonymize_dataframe_replaces_authors() -> None:
    df = pl.DataFrame(
        {
            "author": ["João Silva", "+55 21 99876-5432"],
            "message": ["Message 1", "Message 2"],
            "date": [date(2024, 1, 1), date(2024, 1, 1)],
            "timestamp": [
                datetime(2024, 1, 1, 12, 0),
                datetime(2024, 1, 1, 13, 0),
            ],
        }
    )

    anonymized_df = Anonymizer.anonymize_dataframe(df, format="full")
    authors = anonymized_df["author"].to_list()

    assert all(len(name) == UUID_FULL_LENGTH for name in authors)
    assert all(uuid.UUID(name) for name in authors)
