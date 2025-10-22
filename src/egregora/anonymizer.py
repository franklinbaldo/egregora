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
        """Return a deterministic UUIDv5 pseudonym for any author string.
        
        Naive approach: Always use nickname namespace to avoid regex complexity.
        This ensures ALL authors get anonymized regardless of format.
        """
        # Naive anonymization - always treat as nickname to ensure anonymization
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

        authors = (
            df.select(pl.col("author")).drop_nulls().unique().get_column("author").to_list()
        )

        if authors:
            author_lookup = pl.DataFrame(
                {
                    "author": authors,
                    "__author_display__": [
                        Anonymizer.anonymize_author(value, format) for value in authors
                    ],
                }
            )
            result = df.join(author_lookup, on="author", how="left")
            anonymized_author = pl.col("__author_display__")
        else:
            result = df
            anonymized_author = pl.lit(None, dtype=pl.String)

        result = result.with_columns(
            pl.when(pl.col("author").is_null())
            .then(pl.lit(None, dtype=pl.String))
            .otherwise(pl.coalesce([anonymized_author, pl.format("{}", pl.col("author"))]))
            .alias("author")
        )

        if "__author_display__" in result.columns:
            result = result.drop("__author_display__")

        content_columns = [
            column
            for column in ("message", "original_line", "tagged_line")
            if column in df.columns
        ]

        if not content_columns:
            return result

        mention_pattern = r"@?\u2068(.*?)\u2069"
        phone_pattern = (
            r"(?:\+\d{2}\s?\d{2}\s?\d{4,5}-?\d{4}"
            r"|\+\d{1,4}\s?\(\d{3,4}\)\s?\d{3,4}-\d{4}"
            r"|\+\d{2}\s?\d{4}\s?\d{6}"
            r"|\+\d{1,4}\s?\d{3,4}\s?\d{3,4}\s?\d{3,4}"
            r"|\b\d{4,5}-\d{4}\b)"
        )

        def _collect_unique(exprs: list[pl.Expr], alias: str) -> pl.Series:
            if not exprs:
                return pl.Series(alias, [], dtype=pl.String)

            aggregated = (
                df.select(pl.concat_list(exprs).alias(alias))
                .explode(alias)
                .explode(alias)
                .drop_nulls()
                .with_columns(pl.col(alias).str.strip_chars().alias(alias))
                .filter(pl.col(alias).str.lengths() > 0)
                .select(alias)
                .unique()
            )
            return aggregated.get_column(alias)

        mention_series = _collect_unique(
            [
                pl.col(column).cast(pl.Utf8).str.extract_all(mention_pattern)
                for column in content_columns
            ],
            "mention",
        )
        phone_series = _collect_unique(
            [
                pl.col(column).cast(pl.Utf8).str.extract_all(phone_pattern)
                for column in content_columns
            ],
            "phone",
        )

        mention_labels = mention_series.to_list()
        phone_numbers = phone_series.to_list()

        link_base = profile_link_base.rstrip("/") if profile_link_base else "profiles"

        if mention_labels:
            mention_lookup = pl.DataFrame(
                {
                    "label": mention_labels,
                    "display": [
                        Anonymizer.anonymize_author(label, format) for label in mention_labels
                    ],
                    "uuid_full": [
                        Anonymizer.anonymize_author(label, "full") for label in mention_labels
                    ],
                }
            ).with_columns(
                pl.col("label")
                .str.replace_all(r"([\\.\^$*+?{}\[\]|()\-])", r"\\$1")
                .alias("escaped_label"),
                pl.concat_str(
                    [pl.lit("@?\\u2068"), pl.col("escaped_label"), pl.lit("\\u2069")]
                ).alias("pattern"),
                pl.concat_str(
                    [
                        pl.format(
                            "[@{}]({}/{})",
                            pl.col("display"),
                            pl.lit(link_base),
                            pl.col("uuid_full"),
                        ),
                        pl.lit(".md"),
                    ]
                ).alias("replacement"),
                pl.col("label").str.len_bytes().alias("__len"),
            ).sort("__len", descending=True)
            mention_structs = list(
                zip(
                    mention_lookup.get_column("pattern").to_list(),
                    mention_lookup.get_column("replacement").to_list(),
                )
            )
        else:
            mention_structs = []

        if phone_numbers:
            phone_lookup = pl.DataFrame(
                {
                    "original": phone_numbers,
                    "anonymized": [
                        Anonymizer.anonymize_phone(number, format) for number in phone_numbers
                    ],
                }
            ).with_columns(
                pl.col("original")
                .str.replace_all(r"([\\.\^$*+?{}\[\]|()\-])", r"\\$1")
                .alias("pattern"),
                pl.col("original").str.len_bytes().alias("__len"),
            ).sort("__len", descending=True)
            phone_structs = list(
                zip(
                    phone_lookup.get_column("pattern").to_list(),
                    phone_lookup.get_column("anonymized").to_list(),
                )
            )
        else:
            phone_structs = []

        def _apply_replacements(expr: pl.Expr, replacements: list[tuple[str, str]]) -> pl.Expr:
            if not replacements:
                return expr

            return pl.fold(
                acc=expr,
                exprs=[
                    pl.struct(
                        pl.lit(pattern).alias("pattern"),
                        pl.lit(replacement).alias("replacement"),
                    )
                    for pattern, replacement in replacements
                ],
                function=lambda acc, data: acc.str.replace_all(data["pattern"], data["replacement"]),
            )

        def build_content_expr(column: str) -> pl.Expr:
            expr = pl.col(column).cast(pl.Utf8)
            expr = _apply_replacements(expr, mention_structs)
            expr = _apply_replacements(expr, phone_structs)
            expr = expr.str.replace_all("\u2068", "").str.replace_all("\u2069", "")
            return (
                pl.when(pl.col(column).is_null())
                .then(pl.lit(None, dtype=pl.String))
                .otherwise(expr)
                .alias(column)
            )

        return result.with_columns([build_content_expr(column) for column in content_columns])

    @staticmethod
    def anonymize_series(
        series: pl.Series,
        format: FormatType = "human",
    ) -> pl.Series:
        """Return a new Polars series with anonymized author names."""

        dataframe = pl.DataFrame({"author": series})
        return Anonymizer.anonymize_dataframe(dataframe, format=format)["author"]

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

            # Always create link to profiles/{user_uuid}.md
            full_uuid = Anonymizer.anonymize_author(label, "full")
            base_path = profile_link_base.rstrip("/") if profile_link_base else "profiles"
            link = f"{base_path}/{full_uuid}.md"
            return f"[{display}]({link})"

        sanitized = Anonymizer._MENTION_PATTERN.sub(_replace, text)
        return sanitized.replace("\u2068", "").replace("\u2069", "")


__all__ = ["Anonymizer", "FormatType"]
