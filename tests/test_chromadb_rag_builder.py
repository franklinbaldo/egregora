from __future__ import annotations

from datetime import date, datetime
import sys
import sys
import types
from datetime import date, datetime
from types import SimpleNamespace

import pytest

pl = pytest.importorskip("polars")

try:  # pragma: no cover - dependency shim for unit tests
    import chromadb  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - executed in CI without chromadb
    chromadb = types.ModuleType("chromadb")  # type: ignore
    chromadb.PersistentClient = object  # type: ignore[attr-defined]
    chromadb.utils = types.ModuleType("utils")  # type: ignore[attr-defined]
    chromadb.utils.embedding_functions = types.SimpleNamespace()  # type: ignore[attr-defined]
    sys.modules["chromadb"] = chromadb
    sys.modules["chromadb.utils"] = chromadb.utils

if "dateutil" not in sys.modules:  # pragma: no cover - shim heavy optional dependency
    dateutil = types.ModuleType("dateutil")
    dateutil_parser = types.ModuleType("parser")
    dateutil_parser.parse = lambda value, *_, **__: value  # type: ignore[attr-defined]
    dateutil.parser = dateutil_parser  # type: ignore[attr-defined]
    sys.modules["dateutil"] = dateutil
    sys.modules["dateutil.parser"] = dateutil_parser

if "diskcache" not in sys.modules:  # pragma: no cover - optional runtime dependency
    diskcache = types.ModuleType("diskcache")
    diskcache.Cache = object  # type: ignore[attr-defined]
    sys.modules["diskcache"] = diskcache

from egregora.rag.chromadb_rag import _MessageEmbeddingBuilder


def _sample_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [
                datetime(2024, 5, 20, 9, 0),
                datetime(2024, 5, 20, 9, 5),
                datetime(2024, 5, 20, 9, 10),
                datetime(2024, 5, 21, 8, 0),
            ],
            "author": ["Alice", "", None, "Bob"],
            "message": [
                "Bom dia!",
                "Tudo bem?",
                "Vamos começar a reunião.",
                "Seguem os relatórios.",
            ],
            "date": [
                date(2024, 5, 20),
                date(2024, 5, 20),
                date(2024, 5, 20),
                date(2024, 5, 21),
            ],
        }
    )


def test_message_embedding_builder_outputs_are_stable() -> None:
    config = SimpleNamespace(
        message_context_radius_before=1,
        message_context_radius_after=1,
    )

    builder = _MessageEmbeddingBuilder(
        config=config,
        group_slug="grupo-teste",
        message_uuid=lambda **kwargs: "|".join(
            [
                kwargs["group_slug"],
                kwargs["timestamp"].isoformat() if kwargs["timestamp"] else "",
                kwargs["author"],
                kwargs["message"],
            ]
        ),
        timestamp_formatter=lambda value: value.isoformat() if value else "",
    )

    batch = builder.build(_sample_frame())

    expected_inputs = [
        "<target_message>09:00 — Alice: Bom dia!</target_message>\n"
        "09:05 — (autor desconhecido): Tudo bem?",
        "09:00 — Alice: Bom dia!\n"
        "<target_message>09:05 — (autor desconhecido): Tudo bem?</target_message>\n"
        "09:10 — (autor desconhecido): Vamos começar a reunião.",
        "09:05 — (autor desconhecido): Tudo bem?\n"
        "<target_message>09:10 — (autor desconhecido): Vamos começar a reunião.</target_message>",
        "<target_message>08:00 — Bob: Seguem os relatórios.</target_message>",
    ]

    assert batch.inputs == expected_inputs

    expected_metadatas = [
        {
            "kind": "message",
            "group_slug": "grupo-teste",
            "timestamp": "2024-05-20T09:00:00",
            "message_index": 0,
            "context_start": 0,
            "context_end": 1,
            "date": "2024-05-20",
        },
        {
            "kind": "message",
            "group_slug": "grupo-teste",
            "timestamp": "2024-05-20T09:05:00",
            "message_index": 1,
            "context_start": 0,
            "context_end": 2,
            "date": "2024-05-20",
        },
        {
            "kind": "message",
            "group_slug": "grupo-teste",
            "timestamp": "2024-05-20T09:10:00",
            "message_index": 2,
            "context_start": 1,
            "context_end": 2,
            "date": "2024-05-20",
        },
        {
            "kind": "message",
            "group_slug": "grupo-teste",
            "timestamp": "2024-05-21T08:00:00",
            "message_index": 0,
            "context_start": 0,
            "context_end": 0,
            "date": "2024-05-21",
        },
    ]

    assert batch.metadatas == expected_metadatas

    assert list(batch.cache_entries.keys()) == [
        ("grupo-teste", "2024-05-20"),
        ("grupo-teste", "2024-05-21"),
    ]

