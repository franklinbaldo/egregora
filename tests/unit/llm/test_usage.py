"""Unit tests for the UsageTracker class."""

from pydantic_ai.usage import RunUsage

from egregora.llm.usage import UsageTracker


def test_usage_tracker_initialization():
    """Test that UsageTracker initializes with empty usage and history."""
    tracker = UsageTracker()
    assert tracker.usage.total_tokens == 0
    assert tracker.usage.input_tokens == 0
    assert tracker.usage.output_tokens == 0
    assert len(tracker.history) == 0


def test_usage_tracker_record_single():
    """Test recording a single usage entry."""
    tracker = UsageTracker()
    usage1 = RunUsage(input_tokens=10, output_tokens=20)
    tracker.record(usage1)

    assert tracker.usage.total_tokens == 30
    assert tracker.usage.input_tokens == 10
    assert tracker.usage.output_tokens == 20
    assert len(tracker.history) == 1
    assert tracker.history[0] == usage1


def test_usage_tracker_record_multiple():
    """Test that multiple usage entries are aggregated correctly."""
    tracker = UsageTracker()
    usage1 = RunUsage(input_tokens=10, output_tokens=20)
    usage2 = RunUsage(input_tokens=5, output_tokens=15)
    tracker.record(usage1)
    tracker.record(usage2)

    assert tracker.usage.total_tokens == 50
    assert tracker.usage.input_tokens == 15
    assert tracker.usage.output_tokens == 35
    assert len(tracker.history) == 2
    assert tracker.history[0] == usage1
    assert tracker.history[1] == usage2


def test_usage_tracker_history_truncation():
    """Test that the history deque is truncated at max_history (50)."""
    tracker = UsageTracker()
    max_history = 50

    for i in range(max_history + 10):
        usage = RunUsage(input_tokens=i, output_tokens=i)
        tracker.record(usage)

    assert len(tracker.history) == max_history
    # The first element should be the 10th one recorded (index 10)
    assert tracker.history[0].input_tokens == 10
    # The last element should be the last one recorded
    assert tracker.history[-1].input_tokens == max_history + 9
