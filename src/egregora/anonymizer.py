"""Deterministic anonymization helpers for authors and identifiers."""

from __future__ import annotations

import re
import uuid
from typing import Literal

import polars as pl

BRAZIL_MOBILE_WITH_PREFIX_LENGTH = 13
BRAZIL_COUNTRY_PREFIX = "55"

FormatType = Literal["human", "short", "full"]


class Anonymizer:
    """Create deterministic pseudonyms for phones and nicknames."""

    # Namespaces derived from RFC 4122 example UUIDs, but with stable values
    # dedicated to the project so collisions between phone and nickname inputs
    # are impossible.
    NAMESPACE_PHONE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    NAMESPACE_NICKNAME = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c9")
    _MENTION_PATTERN = re.compile(r"(?P<prefix>@?)\u2068(?P<label>.*?)\u2069")

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Return a normalized representation of *phone*.

        The normalization removes spaces, hyphens and parentheses while keeping
        the leading ``+`` if present. Phone numbers without ``+`` are assumed to
        be Brazilian numbers (``+55``) when they contain 10 or 11 digits.
        """
        # TODO: The logic to assume Brazilian numbers is hardcoded. This should be
        # made more generic or configurable if the tool is to be used in other regions.
        normalized = re.sub(r"[^\d+]", "", phone)
        if not normalized:
            return ""

        if normalized.startswith("+"):
            return normalized

        digits_only = re.sub(r"\D", "", normalized)
        if len(digits_only) in {10, 11}:
            return "+55" + digits_only
        if len(digits_only) == BRAZIL_MOBILE_WITH_PREFIX_LENGTH and digits_only.startswith(
            BRAZIL_COUNTRY_PREFIX
        ):
            return "+" + digits_only
        return digits_only

    @staticmethod
    def normalize_nickname(nickname: str) -> str:
        """Normalize *nickname* by stripping duplicated whitespace and casing."""

        return " ".join(nickname.strip().lower().split())

    @staticmethod
    def _format_uuid(uuid_str: str, prefix: str, format: FormatType) -> str:
        """Return ``uuid_str`` in the requested format."""

        if format == "human":
            short = uuid_str.split("-")[0][:4].upper()
            return f"{prefix}-{short}"
        elif format == "short":
            return uuid_str.split("-")[0][:8].lower()
        elif format == "full":
            return uuid_str
        else:
            raise ValueError(f"Unknown format: {format}")

    @staticmethod
    def anonymize_phone(
        phone: str,
        format: FormatType = "human",
        prefix: str = "Member",
    ) -> str:
        """Return a deterministic pseudonym for ``phone``.

        ``prefix`` allows configuring the human-friendly prefix to keep the
        anonymized format aligned with nickname anonymization.
        """

        normalized = Anonymizer.normalize_phone(phone)
        uuid_full = str(uuid.uuid5(Anonymizer.NAMESPACE_PHONE, normalized))
        return Anonymizer._format_uuid(uuid_full, prefix, format)

    @staticmethod
    def anonymize_nickname(
        nickname: str,
        format: FormatType = "human",
        prefix: str = "Member",
    ) -> str:
        """Return a deterministic pseudonym for ``nickname``."""

        normalized = Anonymizer.normalize_nickname(nickname)
        uuid_full = str(uuid.uuid5(Anonymizer.NAMESPACE_NICKNAME, normalized))
        return Anonymizer._format_uuid(uuid_full, prefix, format)

    @staticmethod
    def anonymize_author(author: str, format: FormatType = "human") -> str:
        """Return a deterministic pseudonym for either a phone or nickname."""
        # TODO: The heuristic to distinguish between a phone number and a nickname
        # is simple and might misclassify nicknames that are all digits. This is a
        # trade-off between simplicity and accuracy. A more robust solution could
        # involve more sophisticated pattern matching or configuration.
        candidate = author.strip().replace(" ", "").replace("-", "")
        if candidate.startswith("+") or candidate.isdigit():
            return Anonymizer.anonymize_phone(author, format)
        return Anonymizer.anonymize_nickname(author, format)

    @staticmethod
    def get_uuid_variants(identifier: str) -> dict[str, str]:
        """Return the three supported representations for ``identifier``."""

        variants: dict[str, str] = {}
        candidate = identifier.strip().replace(" ", "").replace("-", "")
        if candidate.startswith("+") or candidate.isdigit():
            variants["human"] = Anonymizer.anonymize_phone(identifier, "human")
            variants["short"] = Anonymizer.anonymize_phone(identifier, "short")
            variants["full"] = Anonymizer.anonymize_phone(identifier, "full")
        else:
            variants["human"] = Anonymizer.anonymize_nickname(identifier, "human")
            variants["short"] = Anonymizer.anonymize_nickname(identifier, "short")
            variants["full"] = Anonymizer.anonymize_nickname(identifier, "full")
        return variants

    @staticmethod
    def anonymize_dataframe(
        df: pl.DataFrame,
        format: FormatType = "human",
        *,
        profile_link_base: str | None = None,
    ) -> pl.DataFrame:
        """Return a new DataFrame with the ``author`` column anonymized."""

        if "author" not in df.columns:
            raise KeyError("DataFrame must have 'author' column")

        result = df.with_columns(
            pl.col("author").map_elements(
                lambda author: Anonymizer.anonymize_author(author, format),
                return_dtype=pl.String,
            )
        )

        def _map_content(value: str | None) -> str | None:
            # First anonymize mentions
            text = Anonymizer.anonymize_mentions(
                value,
                format=format,
                profile_link_base=profile_link_base,
            )
            # Then anonymize phone numbers in content
            return Anonymizer.anonymize_phone_numbers_in_text(text, format=format)

        for column in ("message", "original_line", "tagged_line"):
            if column in result.columns:
                result = result.with_columns(
                    pl.col(column).map_elements(_map_content, return_dtype=pl.String).alias(column)
                )

        return result

    @staticmethod
    def anonymize_series(
        series: pl.Series,
        format: FormatType = "human",
    ) -> pl.Series:
        """Return a new Polars series with anonymized author names."""

        return series.map_elements(
            lambda author: Anonymizer.anonymize_author(author, format),
            return_dtype=pl.String,
        )

    @staticmethod
    def anonymize_phone_numbers_in_text(
        text: str | None,
        *,
        format: FormatType = "full",
    ) -> str | None:
        """Replace phone numbers in text content with anonymized equivalents."""
        
        if text is None or not isinstance(text, str):
            return text
            
        # Patterns to match phone numbers in text content
        phone_patterns = [
            r'\+\d{2}\s?\d{2}\s?\d{4,5}-?\d{4}',  # Brazilian format like +55 11 98594-0512
            r'\+\d{1,4}\s?\(\d{3,4}\)\s?\d{3,4}-\d{4}',  # US format like +1 (415) 656-5918
            r'\+\d{2}\s?\d{4}\s?\d{6}',  # UK format like +44 7502 313434
            r'\+\d{1,4}\s?\d{3,4}\s?\d{3,4}\s?\d{3,4}',  # General international format
            r'\b\d{4,5}-\d{4}\b',  # Local format like 98594-0512
        ]
        
        result = text
        for pattern in phone_patterns:
            def _replace_phone(match: re.Match[str]) -> str:
                phone_number = match.group(0)
                return Anonymizer.anonymize_phone(phone_number, format)
            
            result = re.sub(pattern, _replace_phone, result)
        
        return result

    @staticmethod
    def anonymize_mentions(
        text: str | None,
        *,
        format: FormatType = "human",
        profile_link_base: str | None = None,
    ) -> str | None:
        """Replace WhatsApp mention isolates with anonymized equivalents."""

        if text is None or not isinstance(text, str):
            return text

        def _replace(match: re.Match[str]) -> str:
            prefix = match.group("prefix") or "@"
            label = match.group("label").strip()
            if not label:
                return prefix
            pseudonym = Anonymizer.anonymize_author(label, format)
            display = f"{prefix}{pseudonym}" if prefix else pseudonym

            if profile_link_base:
                full_uuid = Anonymizer.anonymize_author(label, "full")
                base = profile_link_base.rstrip("/")
                if not base:
                    base = "/"
                link = f"{base}/{full_uuid}"
                return f"[{display}]({link})"

            return display

        sanitized = Anonymizer._MENTION_PATTERN.sub(_replace, text)
        return sanitized.replace("\u2068", "").replace("\u2069", "")


__all__ = ["Anonymizer", "FormatType"]
