"""Deterministic anonymization helpers for authors and identifiers."""

from __future__ import annotations

import re
import uuid
from typing import Literal

import polars as pl

DEFAULT_MIN_PHONE_DIGITS = 10

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
        """Return only the numeric digits contained in *phone*."""

        return re.sub(r"\D", "", phone)

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
        digits_only = re.sub(r"\D", "", candidate)
        if candidate.startswith("+") or len(digits_only) >= DEFAULT_MIN_PHONE_DIGITS:
            return Anonymizer.anonymize_phone(author, format)
        return Anonymizer.anonymize_nickname(author, format)

    @staticmethod
    def get_uuid_variants(identifier: str) -> dict[str, str]:
        """Return the three supported representations for ``identifier``."""

        variants: dict[str, str] = {}
        candidate = identifier.strip().replace(" ", "").replace("-", "")
        digits_only = re.sub(r"\D", "", candidate)
        if candidate.startswith("+") or len(digits_only) >= DEFAULT_MIN_PHONE_DIGITS:
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

        def _map_mentions(value: str | None) -> str | None:
            return Anonymizer.anonymize_mentions(
                value,
                format=format,
                profile_link_base=profile_link_base,
            )

        for column in ("message", "original_line", "tagged_line"):
            if column in result.columns:
                result = result.with_columns(
                    pl.col(column).map_elements(_map_mentions, return_dtype=pl.String).alias(column)
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