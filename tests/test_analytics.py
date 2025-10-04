from datetime import date, datetime

import polars as pl

from egregora.analytics import (
    analyze_daily_activity,
    analyze_hourly_activity,
    calculate_gini,
    detect_emerging_topics,
    detect_threads,
    get_conversation_health,
    get_interaction_matrix,
)


def _sample_dataframe() -> pl.DataFrame:
    timestamps = [
        datetime(2024, 1, 1, 8, 0),
        datetime(2024, 1, 1, 8, 5),
        datetime(2024, 1, 1, 9, 0),
        datetime(2024, 1, 2, 7, 30),
        datetime(2024, 1, 2, 8, 45),
    ]
    dates = [dt.date() for dt in timestamps]
    authors = ["Member-A", "Member-B", "Member-A", "Member-C", "Member-B"]
    messages = [
        "Bom dia, equipe!",
        "Vamos revisar o plano de hoje?",
        "Sim, foco nas entregas do trimestre.",
        "Relatório enviado para vocês.",
        "Recebido, obrigado!",
    ]

    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "date": dates,
            "author": authors,
            "message": messages,
        }
    )


def test_get_conversation_health_basic_metrics() -> None:
    df = _sample_dataframe()

    metrics = get_conversation_health(df)

    assert metrics["total_messages"] == 5
    assert metrics["active_participants"] == 3
    assert metrics["thread_count"] >= 1
    assert metrics["messages_per_day_avg"] > 0


def test_calculate_gini_handles_balanced_distribution() -> None:
    series = pl.Series([5, 5, 5, 5])
    assert calculate_gini(series) == 0.0

    unbalanced = pl.Series([1, 1, 1, 9])
    gini = calculate_gini(unbalanced)
    assert 0 < gini < 1


def test_detect_threads_respects_gaps() -> None:
    df = pl.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 1, 8, 0),
                datetime(2024, 1, 1, 8, 10),
                datetime(2024, 1, 1, 9, 0),
            ],
            "date": [date(2024, 1, 1)] * 3,
            "author": ["Member-A", "Member-B", "Member-A"],
            "message": ["Oi", "Tudo bem?", "Sim, e você?"],
        }
    )

    threaded = detect_threads(df, max_gap_minutes=15)
    assert threaded.get_column("thread_id").to_list() == [1, 1, 2]


def test_get_interaction_matrix_builds_pairs() -> None:
    df = _sample_dataframe()

    interactions = get_interaction_matrix(df)
    assert not interactions.is_empty()
    assert set(interactions.columns) == {
        "author",
        "replied_to",
        "interaction_count",
    }


def test_detect_emerging_topics_highlight_growth() -> None:
    df = pl.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 2, 10, 0),
                datetime(2024, 1, 3, 11, 0),
                datetime(2024, 1, 9, 8, 0),
                datetime(2024, 1, 10, 9, 0),
            ],
            "date": [
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 9),
                date(2024, 1, 10),
            ],
            "author": ["A", "B", "C", "A", "B"],
            "message": [
                "alpha beta",
                "alpha alpha",
                "beta gamma",
                "delta delta alpha",
                "delta cresce delta",
            ],
        }
    )

    topics = detect_emerging_topics(df, recent_days=3, growth_ratio_threshold=1.5, min_recent_mentions=2)
    assert "delta" in topics.get_column("word").to_list()


def test_activity_groupings_return_expected_columns() -> None:
    df = _sample_dataframe()

    hourly = analyze_hourly_activity(df)
    daily = analyze_daily_activity(df)

    assert set(hourly.columns) == {"hour", "message_count"}
    assert set(daily.columns) == {"date", "message_count"}
