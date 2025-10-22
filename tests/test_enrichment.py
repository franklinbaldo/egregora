from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("pydantic_ai")

import polars as pl

from egregora.enrichment import (
    extract_urls_from_dataframe,
    get_url_contexts_dataframe,
)


def _build_frame() -> pl.DataFrame:
    base_time = datetime(2024, 1, 1, 9, 0)
    timestamps = [base_time + timedelta(minutes=5 * i) for i in range(5)]
    times = [ts.strftime("%H:%M") for ts in timestamps]
    authors = ["Alice", "Bruno", "Carla", "Daniel", "Eva"]
    messages = [
        "Primeiro link http://alpha.test",
        "Dois links http://beta.test e http://gamma.test",
        "Mensagem sem link",
        "Outro link aparece em http://delta.test",
        "Encerrando sem links",
    ]
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "time": times,
            "author": authors,
            "message": messages,
        }
    )


def _format_messages(times: list[str], authors: list[str], messages: list[str]) -> list[str]:
    return [f"{t} — {a}: {m}".strip() for t, a, m in zip(times, authors, messages, strict=False)]


def test_get_url_contexts_dataframe_multiple_urls_and_windows() -> None:
    frame = _build_frame()
    frame_with_urls = extract_urls_from_dataframe(frame)

    result_window_1 = get_url_contexts_dataframe(frame_with_urls, context_window=1)
    result_window_2 = get_url_contexts_dataframe(frame_with_urls, context_window=2)

    formatted = _format_messages(
        frame.get_column("time").to_list(),
        frame.get_column("author").to_list(),
        frame.get_column("message").to_list(),
    )

    expected_window_1 = [
        {
            "url": "http://alpha.test",
            "timestamp": frame.get_column("timestamp")[0],
            "author": "Alice",
            "message": frame.get_column("message")[0],
            "context_before": "",
            "context_after": formatted[1],
        },
        {
            "url": "http://beta.test",
            "timestamp": frame.get_column("timestamp")[1],
            "author": "Bruno",
            "message": frame.get_column("message")[1],
            "context_before": formatted[0],
            "context_after": formatted[2],
        },
        {
            "url": "http://gamma.test",
            "timestamp": frame.get_column("timestamp")[1],
            "author": "Bruno",
            "message": frame.get_column("message")[1],
            "context_before": formatted[0],
            "context_after": formatted[2],
        },
        {
            "url": "http://delta.test",
            "timestamp": frame.get_column("timestamp")[3],
            "author": "Daniel",
            "message": frame.get_column("message")[3],
            "context_before": formatted[2],
            "context_after": formatted[4],
        },
    ]

    expected_window_2 = [
        {
            "url": "http://alpha.test",
            "timestamp": frame.get_column("timestamp")[0],
            "author": "Alice",
            "message": frame.get_column("message")[0],
            "context_before": "",
            "context_after": "\n".join(formatted[1:3]),
        },
        {
            "url": "http://beta.test",
            "timestamp": frame.get_column("timestamp")[1],
            "author": "Bruno",
            "message": frame.get_column("message")[1],
            "context_before": formatted[0],
            "context_after": "\n".join(formatted[2:4]),
        },
        {
            "url": "http://gamma.test",
            "timestamp": frame.get_column("timestamp")[1],
            "author": "Bruno",
            "message": frame.get_column("message")[1],
            "context_before": formatted[0],
            "context_after": "\n".join(formatted[2:4]),
        },
        {
            "url": "http://delta.test",
            "timestamp": frame.get_column("timestamp")[3],
            "author": "Daniel",
            "message": frame.get_column("message")[3],
            "context_before": "\n".join(formatted[1:3]),
            "context_after": formatted[4],
        },
    ]

    assert result_window_1.to_dicts() == expected_window_1
    assert result_window_2.to_dicts() == expected_window_2
