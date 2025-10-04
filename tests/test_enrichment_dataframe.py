from datetime import date, datetime

import polars as pl

from egregora.enrichment import extract_urls_from_dataframe, get_url_contexts_dataframe


def test_extract_urls_creates_list_column() -> None:
    df = pl.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, 9, 0)],
            "date": [date(2024, 1, 1)],
            "time": ["09:00"],
            "author": ["Member-AAAA"],
            "message": ["Confira https://example.com para mais detalhes"],
        }
    )

    enriched = extract_urls_from_dataframe(df)

    assert "urls" in enriched.columns
    assert enriched.get_column("urls").to_list()[0] == ["https://example.com"]


def test_get_url_contexts_dataframe_builds_context() -> None:
    df = pl.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 1, 9, 5),
                datetime(2024, 1, 1, 9, 10),
            ],
            "date": [date(2024, 1, 1)] * 3,
            "time": ["09:00", "09:05", "09:10"],
            "author": ["Member-A", "Member-B", "Member-C"],
            "message": [
                "Primeira mensagem sem link",
                "Link importante: https://egregora.dev",
                "Fechamento da conversa",
            ],
        }
    )

    df_with_urls = extract_urls_from_dataframe(df)
    contexts = get_url_contexts_dataframe(df_with_urls, context_window=1)

    assert contexts.height == 1
    row = contexts.row(0, named=True)
    assert row["url"] == "https://egregora.dev"
    assert "Primeira mensagem" in row["context_before"]
    assert "Fechamento" in row["context_after"]
