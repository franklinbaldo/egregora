"""Simple UUID5-based anonymization for authors and mentions.

Privacy-first approach: All author names are converted to UUID5 pseudonyms
before any LLM interaction. This ensures real names never reach the LLM.

Documentation:
- Privacy & Anonymization: docs/features/anonymization.md
- Architecture (Privacy Boundary): docs/guides/architecture.md#2-anonymizer-anonymizerpy
- Core Concepts: docs/getting-started/concepts.md#privacy-model
"""

from __future__ import annotations

import re
import uuid
from importlib import import_module
from typing import (
    Callable,
    Mapping,
    ParamSpec,
    Protocol,
    Sequence,
    TypeVar,
    cast,
    overload,
    runtime_checkable,
)

_P = ParamSpec("_P")
_R = TypeVar("_R")


class SeriesLike(Protocol):
    """A minimal pandas-like series interface used for author extraction."""

    def dropna(self) -> SeriesLike:
        ...

    def tolist(self) -> list[str]:
        ...


@runtime_checkable
class ColumnExpression(Protocol):
    """Subset of ibis column expression methods used by the anonymizer."""

    def substitute(self, mapping: Mapping[str, str], *, else_: str) -> ColumnExpression:
        ...


class DataFrameLike(Protocol):
    """A minimal dataframe abstraction produced by ``Table.execute``."""

    def __getitem__(self, key: str) -> SeriesLike:
        ...


class Table(Protocol):
    """Interface describing the ibis table operations relied upon here."""

    columns: Sequence[str]

    def select(self, *columns: str) -> Table:
        ...

    def distinct(self) -> Table:
        ...

    def execute(self) -> DataFrameLike:
        ...

    def mutate(self, *args: object, **assignments: ColumnExpression | str) -> Table:
        ...

    def __getattr__(self, name: str) -> ColumnExpression:
        ...


class ScalarNamespace(Protocol):
    """Protocol for ``ibis.udf.scalar`` interactions."""

    def python(self, func: Callable[_P, _R]) -> Callable[_P, _R]:
        ...


class UdfNamespace(Protocol):
    scalar: ScalarNamespace


class IbisModule(Protocol):
    udf: UdfNamespace


def _get_ibis() -> IbisModule:
    """Import ``ibis`` lazily to keep mypy isolated from heavy dependencies."""

    module = import_module("ibis")
    return cast(IbisModule, module)

NAMESPACE_AUTHOR = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
SYSTEM_AUTHOR = "system"

MENTION_PATTERN = re.compile(r"\u2068(?P<name>.*?)\u2069")


def anonymize_author(author: str) -> str:
    """Generate deterministic UUID5 pseudonym for author."""

    normalized = author.strip().lower()
    author_uuid = uuid.uuid5(NAMESPACE_AUTHOR, normalized)
    return author_uuid.hex[:8]


def anonymize_mentions(text: str) -> str:
    """Replace WhatsApp mentions (Unicode markers) with UUID5 pseudonyms."""

    def replace_mention(match: re.Match[str]) -> str:
        name = match.group("name")
        pseudonym = anonymize_author(name)
        return pseudonym

    return MENTION_PATTERN.sub(replace_mention, text)


def anonymize_dataframe(df: Table) -> Table:
    """Anonymize author column and mentions in message column using vector operations."""

    unique_authors_frame: DataFrameLike = df.select("author").distinct().execute()
    unique_authors_series: SeriesLike = unique_authors_frame["author"]
    unique_authors = unique_authors_series.dropna().tolist()
    author_mapping: dict[str, str] = {
        author: anonymize_author(author) for author in unique_authors
    }

    author_expr: ColumnExpression = df.author
    anonymized_author: ColumnExpression = author_expr.substitute(
        author_mapping, else_=SYSTEM_AUTHOR
    )
    anonymized_df = df.mutate(author=anonymized_author)

    if "message" in anonymized_df.columns:
        ibis_module = _get_ibis()

        @overload
        def anonymize_mentions_udf(text: ColumnExpression) -> ColumnExpression:
            ...

        @overload
        def anonymize_mentions_udf(text: str) -> str:
            ...

        @overload
        def anonymize_mentions_udf(text: None) -> None:
            ...

        @ibis_module.udf.scalar.python
        def anonymize_mentions_udf(
            text: str | None | ColumnExpression,
        ) -> str | None | ColumnExpression:
            """UDF wrapper for anonymize_mentions."""

            if text is None or isinstance(text, ColumnExpression):
                return text
            return anonymize_mentions(str(text))

        anonymized_message = anonymize_mentions_udf(anonymized_df.message)
        anonymized_df = anonymized_df.mutate(message=anonymized_message)

    return anonymized_df
