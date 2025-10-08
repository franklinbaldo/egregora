"""Deterministic anonymization helpers for authors and identifiers."""

from __future__ import annotations

import re
import uuid
from typing import Literal

import polars as pl


FormatType = Literal["human", "short", "full"]


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
        df: pl.DataFrame, format: FormatType = "human"
    ) -> pl.DataFrame:
        """Return a new DataFrame with the ``author`` column anonymized."""

        if "author" not in df.columns:
            raise KeyError("DataFrame must have 'author' column")

        return df.with_columns(
            pl.col("author").map_elements(
                lambda author: Anonymizer.anonymize_author(author, format),
                return_dtype=pl.String,
            )
        )

    @staticmethod
    def anonymize_series(series: pl.Series, format: FormatType = "human") -> pl.Series:
        """Return a new Polars series with anonymized author names."""

        return series.map_elements(
            lambda author: Anonymizer.anonymize_author(author, format),
            return_dtype=pl.String,
        )

    @staticmethod
    def anonymize_transcript_dataframe(
        df: pl.DataFrame, format: FormatType = "human"
    ) -> pl.DataFrame:
        """Return a new DataFrame with the author in 'original_line' anonymized."""
        if "original_line" not in df.columns:
            return df

        # This regex is more robust to handle different timestamp formats
        line_pattern = re.compile(
            r"^(?P<prefix>(?:(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})?[\s,]*?)?\d{1,2}:\d{2}(?:\s*[APap][Mm])?\s*[-–—]\s*)(?P<author>[^:]+?)(?P<suffix>:.*)$"
        )

        def _anonymize_line(line: str) -> str:
            if not isinstance(line, str):
                return line

            match = line_pattern.match(line)
            if not match:
                return line

            prefix = match.group("prefix")
            author = match.group("author").strip()
            suffix = match.group("suffix")

            if author:
                anonymized_author = Anonymizer.anonymize_author(author, format)
                return f"{prefix}{anonymized_author}{suffix}"
            return line

        return df.with_columns(
            pl.col("original_line")
            .map_elements(_anonymize_line, return_dtype=pl.String)
            .alias("original_line")
        )


__all__ = ["Anonymizer", "FormatType"]
