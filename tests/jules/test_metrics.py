import json
import os
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import asdict
from jules.metrics import MetricsCollector, TickMetrics

def test_metrics_collection(tmp_path):
    # Setup
    metrics_file = tmp_path / "metrics/ticks.jsonl"

    # Mock the METRICS_FILE class attribute
    # We need to subclass or patch because it's a class attribute
    class TestMetricsCollector(MetricsCollector):
        METRICS_FILE = metrics_file
        METRICS_DIR = tmp_path / "metrics"

    collector = TestMetricsCollector()

    # Create a metric
    metric = TickMetrics(
        tick_time="2023-01-01T12:00:00Z",
        mode="cycle",
        last_persona_id="p1",
        next_persona_id="p2",
        pr_number=123,
        pr_merged=True,
        sprint_incremented=False
    )

    # Record it
    collector.record_tick(metric)

    # Verify file content
    assert metrics_file.exists()
    content = metrics_file.read_text()
    data = json.loads(content)

    assert data["tick_time"] == "2023-01-01T12:00:00Z"
    assert data["mode"] == "cycle"
    assert data["pr_number"] == 123
    assert data["pr_merged"] is True

def test_get_stats(tmp_path):
    metrics_file = tmp_path / "metrics/ticks.jsonl"
    class TestMetricsCollector(MetricsCollector):
        METRICS_FILE = metrics_file
        METRICS_DIR = tmp_path / "metrics"

    collector = TestMetricsCollector()

    # Add some metrics
    metrics = [
        TickMetrics(tick_time="t1", mode="cycle", error="fail", session_persona="p1"),
        TickMetrics(tick_time="t2", mode="cycle", pr_merged=True, session_persona="p1"),
        TickMetrics(tick_time="t3", mode="cycle", session_id="s1", session_persona="p2"),
    ]

    for m in metrics:
        collector.record_tick(m)

    stats = collector.get_stats()

    assert stats["total_ticks"] == 3
    assert stats["errors"] == 1
    assert stats["prs_merged"] == 1
    assert stats["sessions_created"] == 1
    assert stats["unique_personas"] == 2
    assert stats["most_run_persona"] == ("p1", 2)
