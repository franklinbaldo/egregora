from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.anonymizer import Anonymizer

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
