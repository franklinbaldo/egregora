"""DataFrame-native analytics for conversation health and patterns.

This module provides analytics helpers implemented with `polars` for
analyzing WhatsApp conversation patterns, user interactions, and
conversation health metrics.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any, Dict, Iterable, Sequence

import polars as pl

__all__ = [
    "get_conversation_health",
    "calculate_gini",
    "get_influence_scores",
    "get_interaction_matrix",
    "detect_threads",
    "get_thread_starters",
    "analyze_hourly_activity",
    "analyze_daily_activity",
    "get_participation_timeline",
    "detect_emerging_topics",
]


_EMPTY_INTERACTION_SCHEMA = {
    "author": pl.String,
    "replied_to": pl.String,
    "interaction_count": pl.Int64,
}

def _ensure_series(values: pl.Series | Sequence[float]) -> pl.Series:
    """Return *values* as a Polars series without nulls."""

    if isinstance(values, pl.Series):
        series = values.drop_nulls()
    else:
        series = pl.Series(values).drop_nulls()
    return series


def get_conversation_health(
    df: pl.DataFrame,
    *,
    thread_gap_minutes: int = 30,
) -> Dict[str, Any]:
    """Calculate comprehensive conversation health metrics."""

    if df.is_empty():
        return {}

    total_messages = df.height
    active_participants = df.get_column("author").n_unique()
    date_range = df.get_column("date").max() - df.get_column("date").min()

    messages_per_participant = (
        df.group_by("author").agg(pl.len().alias("message_count"))
    ).get_column("message_count")

    participation_mean = float(messages_per_participant.mean() or 0.0)
    participation_std = float(messages_per_participant.std() or 0.0)

    gini_coefficient = calculate_gini(messages_per_participant)

    df_sorted = df.sort("timestamp")
    response_times = (
        df_sorted.get_column("timestamp").diff().dt.total_seconds() / 60
    )
    response_times = response_times.drop_nulls()
    median_response_time = float(response_times.median() or 0.0)

    df_with_threads = detect_threads(df, max_gap_minutes=thread_gap_minutes)
    thread_count = (
        df_with_threads.get_column("thread_id").n_unique()
        if "thread_id" in df_with_threads.columns
        else 0
    )

    daily_activity = (
        df.group_by("date").agg(pl.len().alias("message_count")).sort("date")
    )
    messages_per_day_avg = float(
        daily_activity.get_column("message_count").mean() or 0.0
    )
    most_active_day = (
        daily_activity.sort("message_count", descending=True)
        .get_column("date")
        .to_list()
    )
    most_active_day_value = most_active_day[0] if most_active_day else None
    max_messages_in_day = (
        daily_activity.get_column("message_count").max() if not daily_activity.is_empty() else 0
    )
    mean_daily = daily_activity.get_column("message_count").mean() or 0.0
    std_daily = daily_activity.get_column("message_count").std() or 0.0
    activity_consistency = float(std_daily / mean_daily) if mean_daily else 0.0

    return {
        "total_messages": total_messages,
        "active_participants": active_participants,
        "messages_per_participant_avg": participation_mean,
        "messages_per_participant_std": participation_std,
        "gini_coefficient": gini_coefficient,
        "response_time_median_minutes": median_response_time,
        "thread_count": thread_count,
        "conversation_span_days": date_range.days if hasattr(date_range, "days") else 0,
        "messages_per_day_avg": messages_per_day_avg,
        "most_active_day": most_active_day_value,
        "max_messages_in_day": max_messages_in_day or 0,
        "activity_consistency": activity_consistency,
    }


def calculate_gini(values: pl.Series | Sequence[float]) -> float:
    """Calculate the Gini coefficient for measuring inequality."""

    series = _ensure_series(values)
    if series.is_empty():
        return 0.0

    total = series.sum()
    if total == 0:
        return 0.0

    sorted_series = series.sort()
    n = sorted_series.len()
    index = pl.Series(range(1, n + 1))
    weighted_sum = (index * sorted_series).sum()
    gini = 2 * weighted_sum / (n * total) - (n + 1) / n
    return float(gini)


def get_influence_scores(df: pl.DataFrame) -> pl.DataFrame:
    """Calculate influence scores for participants."""

    if df.is_empty():
        return pl.DataFrame(
            {
                "author": [],
                "message_count": [],
                "first_seen": [],
                "last_seen": [],
                "threads_started": [],
                "replies_received": [],
                "influence": [],
            },
            schema={
                "author": pl.String,
                "message_count": pl.Int64,
                "first_seen": pl.Datetime,
                "last_seen": pl.Datetime,
                "threads_started": pl.Int64,
                "replies_received": pl.Int64,
                "influence": pl.Float64,
            },
        )

    interaction_matrix = get_interaction_matrix(df)
    thread_starters = get_thread_starters(df)

    author_stats = (
        df.group_by("author")
        .agg(
            pl.len().alias("message_count"),
            pl.col("timestamp").min().alias("first_seen"),
            pl.col("timestamp").max().alias("last_seen"),
        )
        .sort("author")
    )

    thread_counts = (
        thread_starters.to_frame("author")
        .group_by("author")
        .agg(pl.len().alias("threads_started"))
    )

    replies_received = (
        interaction_matrix.group_by("replied_to")
        .agg(pl.col("interaction_count").sum().alias("replies_received"))
        .rename({"replied_to": "author"})
        if not interaction_matrix.is_empty()
        else pl.DataFrame({"author": [], "replies_received": []}, schema={"author": pl.String, "replies_received": pl.Int64})
    )

    author_stats = (
        author_stats
        .join(thread_counts, on="author", how="left")
        .join(replies_received, on="author", how="left")
        .fill_null(0)
        .with_columns(
            pl.col("threads_started").cast(pl.Int64),
            pl.col("replies_received").cast(pl.Int64),
        )
    )

    max_messages = float(author_stats.get_column("message_count").max() or 1)
    max_threads = float(author_stats.get_column("threads_started").max() or 1)
    max_replies = float(author_stats.get_column("replies_received").max() or 1)

    author_stats = author_stats.with_columns(
        (
            (pl.col("message_count") / max_messages * 0.3)
            + (pl.col("threads_started") / max_threads * 0.4)
            + (pl.col("replies_received") / max_replies * 0.3)
        ).alias("influence")
    )

    return author_stats.sort("influence", descending=True)


def get_interaction_matrix(df: pl.DataFrame) -> pl.DataFrame:
    """Build interaction matrix showing who responds to whom."""

    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_INTERACTION_SCHEMA)

    df_sorted = df.sort("timestamp").with_columns(
        pl.col("author").shift().alias("replied_to")
    )
    interactions = df_sorted.filter(pl.col("author") != pl.col("replied_to"))
    if interactions.is_empty():
        return pl.DataFrame(schema=_EMPTY_INTERACTION_SCHEMA)

    return (
        interactions.group_by(["author", "replied_to"])
        .agg(pl.len().alias("interaction_count"))
        .sort("interaction_count", descending=True)
    )


def detect_threads(df: pl.DataFrame, *, max_gap_minutes: int = 30) -> pl.DataFrame:
    """Detect conversation threads based on temporal gaps."""

    if df.is_empty():
        return df.clone()

    df_sorted = df.sort("timestamp")
    df_with_gaps = df_sorted.with_columns(
        (pl.col("timestamp").diff().dt.total_seconds() / 60).alias("gap_minutes")
    )
    df_with_flags = df_with_gaps.with_columns(
        (
            (pl.col("gap_minutes") > max_gap_minutes) | pl.col("gap_minutes").is_null()
        ).alias("new_thread")
    )
    df_with_threads = df_with_flags.with_columns(
        pl.col("new_thread").cast(pl.Int64).cum_sum().alias("thread_id")
    )
    return df_with_threads


def get_thread_starters(df: pl.DataFrame) -> pl.Series:
    """Identify who starts conversation threads."""

    threaded = detect_threads(df)
    if threaded.is_empty():
        return pl.Series([], dtype=pl.String)

    starters = (
        threaded.group_by("thread_id")
        .agg(pl.col("author").first().alias("author"))
        .sort("thread_id")
        .get_column("author")
    )
    return starters


def analyze_hourly_activity(df: pl.DataFrame) -> pl.DataFrame:
    """Analyze message distribution by hour of day."""

    if df.is_empty():
        return pl.DataFrame({"hour": [], "message_count": []}, schema={"hour": pl.Int64, "message_count": pl.Int64})

    return (
        df.with_columns(pl.col("timestamp").dt.hour().alias("hour"))
        .group_by("hour")
        .agg(pl.len().alias("message_count"))
        .sort("hour")
    )


def analyze_daily_activity(df: pl.DataFrame) -> pl.DataFrame:
    """Analyze message distribution by day."""

    if df.is_empty():
        return pl.DataFrame({"date": [], "message_count": []}, schema={"date": pl.Date, "message_count": pl.Int64})

    return (
        df.group_by("date")
        .agg(pl.len().alias("message_count"))
        .sort("date")
    )


def get_participation_timeline(df: pl.DataFrame) -> pl.DataFrame:
    """Get participation timeline showing when each author was active."""

    if df.is_empty():
        return pl.DataFrame(
            {
                "author": [],
                "first_message": [],
                "last_message": [],
                "total_messages": [],
                "active_days": [],
                "activity_span_days": [],
                "messages_per_day": [],
            },
            schema={
                "author": pl.String,
                "first_message": pl.Datetime,
                "last_message": pl.Datetime,
                "total_messages": pl.Int64,
                "active_days": pl.Int64,
                "activity_span_days": pl.Float64,
                "messages_per_day": pl.Float64,
            },
        )

    participation = (
        df.group_by("author")
        .agg(
            pl.col("timestamp").min().alias("first_message"),
            pl.col("timestamp").max().alias("last_message"),
            pl.len().alias("total_messages"),
            pl.col("date").n_unique().alias("active_days"),
        )
        .with_columns(
            (pl.col("last_message") - pl.col("first_message"))
            .dt.total_days()
            .fill_null(0)
            .alias("activity_span_days"),
        )
        .with_columns(
            (
                pl.col("total_messages")
                / pl.when(pl.col("activity_span_days") <= 0)
                .then(1)
                .otherwise(pl.col("activity_span_days"))
            ).alias("messages_per_day")
        )
        .sort("total_messages", descending=True)
    )
    return participation


def detect_emerging_topics(
    df: pl.DataFrame,
    *,
    recent_days: int = 7,
    growth_ratio_threshold: float = 2.0,
    min_recent_mentions: int = 3,
    stopwords: Iterable[str] | None = None,
) -> pl.DataFrame:
    """Detect topics that have grown in importance recently."""

    if df.is_empty():
        return pl.DataFrame({"word": [], "recent_count": [], "historical_count": [], "growth_ratio": []}, schema={"word": pl.String, "recent_count": pl.Int64, "historical_count": pl.Int64, "growth_ratio": pl.Float64})

    recent_threshold = df.get_column("date").max() - timedelta(days=recent_days)
    recent_df = df.filter(pl.col("date") > recent_threshold)
    historical_df = df.filter(pl.col("date") <= recent_threshold)

    if recent_df.is_empty() or historical_df.is_empty():
        return pl.DataFrame({"word": [], "recent_count": [], "historical_count": [], "growth_ratio": []}, schema={"word": pl.String, "recent_count": pl.Int64, "historical_count": pl.Int64, "growth_ratio": pl.Float64})

    words_recent = _tokenize_messages(recent_df.get_column("message"), stopwords)
    words_historical = _tokenize_messages(historical_df.get_column("message"), stopwords)

    recent_counter = Counter(words_recent)
    historical_counter = Counter(words_historical)

    emerging: list[dict[str, Any]] = []
    for word, recent_count in recent_counter.most_common(50):
        historical_count = historical_counter.get(word, 0)
        growth_ratio = recent_count / (historical_count + 1)
        if growth_ratio > growth_ratio_threshold and recent_count >= min_recent_mentions:
            emerging.append(
                {
                    "word": word,
                    "recent_count": recent_count,
                    "historical_count": historical_count,
                    "growth_ratio": float(growth_ratio),
                }
            )

    if not emerging:
        return pl.DataFrame({"word": [], "recent_count": [], "historical_count": [], "growth_ratio": []}, schema={"word": pl.String, "recent_count": pl.Int64, "historical_count": pl.Int64, "growth_ratio": pl.Float64})

    return pl.DataFrame(emerging).sort("growth_ratio", descending=True)


def _tokenize_messages(
    messages: Sequence[str] | pl.Series,
    stopwords: Iterable[str] | None,
) -> list[str]:
    """Tokenize messages using a very small Portuguese stopword list."""

    if stopwords is None:
        stopwords = {
            "o",
            "a",
            "de",
            "que",
            "e",
            "do",
            "da",
            "em",
            "um",
            "para",
            "é",
            "com",
            "não",
            "uma",
            "os",
            "no",
            "se",
            "na",
            "por",
            "mais",
            "as",
            "dos",
            "como",
            "mas",
            "foi",
            "ao",
            "ele",
            "das",
            "tem",
            "à",
            "seu",
            "sua",
            "ou",
            "ser",
            "quando",
            "muito",
            "há",
            "nos",
            "já",
            "está",
            "eu",
            "também",
            "só",
            "pelo",
            "pela",
            "até",
            "isso",
            "ela",
            "entre",
            "era",
            "depois",
            "sem",
            "mesmo",
            "aos",
            "ter",
            "seus",
            "suas",
            "nem",
            "às",
            "meu",
            "minha",
            "numa",
            "pelos",
            "pelas",
            "essa",
            "esse",
            "este",
            "esta",
            "então",
            "ainda",
            "hoje",
            "aqui",
            "agora",
            "sempre",
            "todos",
            "bem",
            "pode",
            "onde",
            "quem",
            "tudo",
            "vai",
            "sim",
            "sobre",
            "vez",
            "tanto",
            "qual",
            "cada",
            "pouco",
            "antes",
            "menos",
            "outro",
            "outra",
            "durante",
            "alguns",
            "algum",
            "dia",
            "tempo",
            "assim",
            "lugar",
            "ano",
            "trabalho",
            "casa",
            "duas",
            "dois",
            "nome",
            "lado",
            "parte",
            "grande",
            "primeiro",
            "primeira",
            "última",
            "último",
            "pessoa",
            "coisa",
            "coisas",
            "novo",
            "nova",
            "toda",
            "todo",
            "nada",
            "vida",
            "país",
            "mão",
            "mãos",
            "nunca",
            "vezes",
            "alta",
            "alto",
            "baixo",
            "baixa",
            "dir",
            "esq",
            "direita",
            "esquerda",
            "faz",
            "fazer",
            "feito",
            "feita",
            "vou",
            "vamos",
            "vai",
            "foram",
            "são",
            "sou",
            "estar",
            "estava",
            "estão",
            "estou",
            "teve",
            "tive",
            "ter",
            "tinha",
            "temos",
            "tenho",
            "fala",
            "falar",
            "falou",
            "disse",
            "dizer",
            "ver",
            "viu",
            "visto",
            "olha",
            "olhar",
            "quer",
            "querer",
            "saber",
            "sei",
            "sabia",
            "sabe",
            "poder",
            "poderia",
            "deve",
            "dever",
            "deveria",
            "gente",
            "pessoal",
            "lá",
            "ali",
        }

    if isinstance(messages, pl.Series):
        iterable: Iterable[str] = messages.to_list()
    else:
        iterable = messages

    result: list[str] = []
    stopwords_set = set(stopwords)
    for message in iterable:
        if not message:
            continue
        for word in message.lower().split():
            word = word.strip()
            if len(word) <= 2 or word in stopwords_set:
                continue
            result.append(word)
    return result
