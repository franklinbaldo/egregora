from datetime import date, datetime

import polars as pl
import pytest

from egregora.anonymizer import Anonymizer, FormatType

ANON_SUFFIX_LENGTH = 4
UUID_FULL_LENGTH = 36
UUID_SHORT_LENGTH = 8


def test_normalize_phone_adds_country_code() -> None:
    assert Anonymizer.normalize_phone("(11) 98765-4321") == "+5511987654321"


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


def test_get_uuid_variants_returns_human_identifier() -> None:
    variants = Anonymizer.get_uuid_variants("Maria")

    assert set(variants.keys()) == {"full", "short", "human"}
    assert variants["human"].startswith("Member-")
    assert len(variants["full"]) == UUID_FULL_LENGTH
    assert len(variants["short"]) == UUID_SHORT_LENGTH


def test_anonymize_dataframe_replaces_authors() -> None:
    df = pl.DataFrame(
        {
            "author": ["João Silva", "+55 21 98765-4322"],
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


@pytest.mark.parametrize("format_", ["human", "short", "full"])
def test_anonymize_dataframe_replaces_mentions_and_phones(format_: FormatType) -> None:
    df = pl.DataFrame(
        {
            "author": ["João Silva"],
            "message": [
                "Olá \u2068Maria\u2069! Ligue 12345-6789 e fale com @\u2068José\u2069.",
            ],
            "original_line": [
                "Contatos: +55 11 91234-5678 e \u2068Maria\u2069",
            ],
        }
    )

    anonymized_df = Anonymizer.anonymize_dataframe(df, format=format_)

    message = anonymized_df["message"][0]
    original_line = anonymized_df["original_line"][0]

    maria_display = Anonymizer.anonymize_author("Maria", format_)
    maria_full = Anonymizer.anonymize_author("Maria", "full")
    jose_display = Anonymizer.anonymize_author("José", format_)
    jose_full = Anonymizer.anonymize_author("José", "full")

    assert "\u2068" not in message
    assert "\u2069" not in message
    assert f"[@{maria_display}](profiles/{maria_full}.md)" in message
    assert f"[@{jose_display}](profiles/{jose_full}.md)" in message

    phone_inline = Anonymizer.anonymize_phone("12345-6789", format=format_)
    phone_with_prefix = Anonymizer.anonymize_phone("+55 11 91234-5678", format=format_)

    assert "12345-6789" not in message
    assert phone_inline in message
    assert "+55 11 91234-5678" not in original_line
    assert phone_with_prefix in original_line


def test_anonymize_dataframe_uses_custom_profile_link_base() -> None:
    df = pl.DataFrame({
        "author": ["Ana"],
        "message": ["Olá @\u2068Bruno\u2069"],
    })

    anonymized_df = Anonymizer.anonymize_dataframe(
        df,
        format="human",
        profile_link_base="team/profiles/",
    )

    bruno_display = Anonymizer.anonymize_author("Bruno", "human")
    bruno_full = Anonymizer.anonymize_author("Bruno", "full")

    assert f"[@{bruno_display}](team/profiles/{bruno_full}.md)" in anonymized_df["message"][0]
