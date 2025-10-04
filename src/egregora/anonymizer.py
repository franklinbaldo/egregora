"""Deterministic anonymization helpers for authors and identifiers."""

from __future__ import annotations

import re
import uuid


class Anonymizer:
    """Create deterministic pseudonyms for phones and nicknames."""

    # Namespaces derived from RFC 4122 example UUIDs, but with stable values
    # dedicated to the project so collisions between phone and nickname inputs
    # are impossible.
    NAMESPACE_PHONE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    NAMESPACE_NICKNAME = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c9")

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Return a normalized representation of *phone*.

        The normalization removes spaces, hyphens and parentheses while keeping
        the leading ``+`` if present. Phone numbers without ``+`` are assumed to
        be Brazilian numbers (``+55``) when they contain 10 or 11 digits.
        """

        normalized = re.sub(r"[^\d+]", "", phone)
        if not normalized:
            return ""

        if normalized.startswith("+"):
            return normalized

        digits_only = re.sub(r"\D", "", normalized)
        if len(digits_only) in {10, 11}:
            return "+55" + digits_only
        if len(digits_only) == 13 and digits_only.startswith("55"):
            return "+" + digits_only
        return digits_only

    @staticmethod
    def normalize_nickname(nickname: str) -> str:
        """Normalize *nickname* by stripping duplicated whitespace and casing."""

        return " ".join(nickname.strip().lower().split())

    @staticmethod
    def _format_human(uuid_str: str, prefix: str) -> str:
        """Return ``uuid_str`` in the canonical human readable format."""

        short = uuid_str.split("-")[0][:4].upper()
        return f"{prefix}-{short}"

    @staticmethod
    def anonymize_phone(phone: str) -> str:
        """Return a deterministic pseudonym for ``phone``."""

        normalized = Anonymizer.normalize_phone(phone)
        uuid_full = str(uuid.uuid5(Anonymizer.NAMESPACE_PHONE, normalized))
        return Anonymizer._format_human(uuid_full, "User")

    @staticmethod
    def anonymize_nickname(nickname: str) -> str:
        """Return a deterministic pseudonym for ``nickname``."""

        normalized = Anonymizer.normalize_nickname(nickname)
        uuid_full = str(uuid.uuid5(Anonymizer.NAMESPACE_NICKNAME, normalized))
        return Anonymizer._format_human(uuid_full, "Member")

    @staticmethod
    def anonymize_author(author: str) -> str:
        """Return a deterministic pseudonym for either a phone or nickname."""

        candidate = author.strip().replace(" ", "").replace("-", "")
        if candidate.startswith("+") or candidate.isdigit():
            return Anonymizer.anonymize_phone(author)
        return Anonymizer.anonymize_nickname(author)

    @staticmethod
    def get_uuid_variants(identifier: str) -> dict[str, str]:
        """Return the canonical representation for ``identifier``."""

        normalized = identifier.strip().replace(" ", "").replace("-", "")
        if normalized.startswith("+") or normalized.isdigit():
            token = Anonymizer.anonymize_phone(identifier)
        else:
            token = Anonymizer.anonymize_nickname(identifier)
        return {"human": token}


__all__ = ["Anonymizer"]
