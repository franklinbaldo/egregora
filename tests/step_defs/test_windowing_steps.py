"""Step definitions for windowing feature."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest
from pytest_bdd import scenarios, given, when, then, parsers
import ibis

from egregora.transformations.windowing import (
    WindowConfig,
    create_windows,
    split_window_into_n_parts,
    generate_window_signature,
)
from egregora.transformations.exceptions import InvalidSplitError, InvalidStepUnitError

scenarios("../features/windowing.feature")


# --- Fixtures ---

@pytest.fixture
def context():
    """Context object to share state between steps."""
    return {}


# --- Given Steps ---

@given(parsers.parse("a message stream with {num_messages:d} messages"))
def given_message_stream_count(context, num_messages):
    start_time = datetime(2023, 1, 1, 10, 0, 0)
    data = [
        {"ts": start_time + timedelta(minutes=i), "text": f"message {i}", "sender": "Alice"}
        for i in range(num_messages)
    ]
    if not data:
         schema = ibis.schema(
            [
                ("ts", "timestamp"),
                ("text", "string"),
                ("sender", "string"),
            ]
        )
         context["table"] = ibis.memtable([], schema=schema)
    else:
        context["table"] = ibis.memtable(data)


@given(parsers.parse("a message stream spanning {minutes:d} minutes with {num_messages:d} messages"))
def given_message_stream_duration(context, minutes, num_messages):
    start_time = datetime(2023, 1, 1, 10, 0, 0)
    interval = minutes / max(1, num_messages)
    data = [
        {"ts": start_time + timedelta(minutes=i * interval), "text": f"message {i}", "sender": "Alice"}
        for i in range(num_messages)
    ]
    context["table"] = ibis.memtable(data)


@given(parsers.parse("a message stream with {num_messages:d} messages averaging {avg_bytes:d} bytes each"))
def given_message_stream_avg_bytes(context, num_messages, avg_bytes):
    text = "x" * avg_bytes
    start_time = datetime(2023, 1, 1, 10, 0, 0)
    data = [
        {"ts": start_time + timedelta(minutes=i), "text": text, "sender": "Alice"}
        for i in range(num_messages)
    ]
    context["table"] = ibis.memtable(data)


@given("a message stream with varying message lengths")
def given_message_stream_varying_lengths(context):
    # Hardcoded data from unit test
    messages = [
        "short",  # 5 bytes
        "medium msg",  # 10 bytes
        "a bit longer message",  # 20 bytes
        "short",  # 5 bytes
        "another medium",  # 14 bytes
    ]
    start_time = datetime(2023, 1, 1, 10, 0, 0)
    data = [
        {"ts": start_time + timedelta(minutes=i), "text": msg, "sender": "Alice"}
        for i, msg in enumerate(messages)
    ]
    context["table"] = ibis.memtable(data)


@given("a message stream with 5 messages where the first 3 share a timestamp")
def given_message_stream_duplicates(context):
    ts = datetime(2023, 1, 1, 10, 0, 0)
    data = [
        {"ts": ts, "text": "a", "sender": "Alice"},
        {"ts": ts, "text": "b", "sender": "Alice"},
        {"ts": ts, "text": "c", "sender": "Alice"},
        {"ts": ts + timedelta(minutes=1), "text": "d", "sender": "Alice"},
        {"ts": ts + timedelta(minutes=1), "text": "e", "sender": "Alice"},
    ]
    context["table"] = ibis.memtable(data)


@given("a single window with 100 messages")
def given_single_window(context):
    given_message_stream_count(context, 100)
    config = WindowConfig(step_size=100, step_unit="messages")
    windows = list(create_windows(context["table"], config=config))
    context["window"] = windows[0]


@given(parsers.parse("a message stream spanning {hours:d} hours with {num_messages:d} messages"))
def given_message_stream_hours(context, hours, num_messages):
    start_time = datetime(2023, 1, 1, 0, 0, 0)
    data = [
        {"ts": start_time + timedelta(hours=i), "text": f"msg {i}", "sender": "A"}
        for i in range(num_messages)
    ]
    context["table"] = ibis.memtable(data)


@given("a valid configuration with writer instructions")
def given_valid_config(context):
    mock_config = MagicMock()
    mock_config.writer.custom_instructions = "instructions"
    mock_config.models.writer = "model-v1"
    context["config"] = mock_config


# --- When Steps ---

@when(parsers.parse("I split the stream by message count with size {step_size:d} and overlap {overlap_ratio:f}"))
def when_split_by_count(context, step_size, overlap_ratio):
    config = WindowConfig(step_size=step_size, step_unit="messages", overlap_ratio=overlap_ratio)
    context["windows"] = list(create_windows(context["table"], config=config))


@when(parsers.parse("I split the stream by time with size {step_size:d} hours and overlap {overlap_ratio:f}"))
def when_split_by_time(context, step_size, overlap_ratio):
    config = WindowConfig(step_size=step_size, step_unit="hours", overlap_ratio=overlap_ratio)
    context["windows"] = list(create_windows(context["table"], config=config))


@when(parsers.parse("I split the stream by bytes with limit {limit:d} and overlap {overlap_ratio:f}"))
def when_split_by_bytes(context, limit, overlap_ratio):
    config = WindowConfig(step_unit="bytes", max_bytes_per_window=limit, overlap_ratio=overlap_ratio)
    context["windows"] = list(create_windows(context["table"], config=config))


@when(parsers.parse("I split the window into {n:d} parts"))
def when_split_window(context, n):
    context["sub_windows"] = split_window_into_n_parts(context["window"], n)


@when(parsers.parse("I try to split with invalid unit \"{unit}\""))
def when_split_invalid_unit(context, unit):
    config = WindowConfig(step_unit=unit)
    try:
        list(create_windows(context["table"], config=config))
    except Exception as e:
        context["exception"] = e


@when(parsers.parse("I try to split the window into {n:d} part"))
def when_split_invalid_n(context, n):
    try:
        split_window_into_n_parts(context["window"], n)
    except Exception as e:
        context["exception"] = e


@when(parsers.parse("I split the stream by \"{unit}\" with size {step_size:d} but max window time {max_hours:d} hours"))
def when_split_max_window(context, unit, step_size, max_hours):
    max_window = timedelta(hours=max_hours)
    config = WindowConfig(step_size=step_size, step_unit=unit, max_window_time=max_window, overlap_ratio=0.0)
    context["windows"] = list(create_windows(context["table"], config=config))


@when(parsers.parse("I generate a signature for the window with template \"{template}\""))
def when_generate_signature(context, template):
    with patch("egregora.transformations.windowing.build_conversation_xml") as mock_build_xml:
        mock_build_xml.return_value = "<chat>content</chat>"
        sig = generate_window_signature(context["table"], context["config"], template)
        context["signature"] = sig


@when("I generate another signature with the same parameters")
def when_generate_signature_again(context):
    with patch("egregora.transformations.windowing.build_conversation_xml") as mock_build_xml:
        mock_build_xml.return_value = "<chat>content</chat>"
        sig = generate_window_signature(context["table"], context["config"], "prompt template")
        context["signature_2"] = sig


# --- Then Steps ---

@then(parsers.parse("I should get {num_windows:d} windows"))
def then_check_window_count(context, num_windows):
    assert len(context["windows"]) == num_windows


@then(parsers.parse("I should get more than {num:d} windows"))
def then_check_min_window_count(context, num):
    assert len(context["windows"]) > num


@then("all windows should have content")
def then_check_windows_content(context):
    for w in context["windows"]:
        assert w.size > 0


@then(parsers.re(r"the window sizes should be (?P<expected_sizes>.*)"))
def then_check_window_sizes(context, expected_sizes):
    if not expected_sizes:
        return
    expected = [int(s.strip()) for s in expected_sizes.split(",")]
    sizes = [w.size for w in context["windows"]]
    assert sizes == expected


@then(parsers.parse("the first window should contain \"{content}\""))
def then_check_first_window_content(context, content):
    expected_list = [s.strip() for s in content.split(",")]
    res = context["windows"][0].table.execute()
    assert res["text"].tolist() == expected_list


@then(parsers.parse("the second window should contain \"{content}\""))
def then_check_second_window_content(context, content):
    expected_list = [s.strip() for s in content.split(",")]
    res = context["windows"][1].table.execute()
    assert res["text"].tolist() == expected_list


@then(parsers.parse("I should get {num:d} sub-windows"))
def then_check_sub_windows(context, num):
    assert len(context["sub_windows"]) == num


@then(parsers.parse("each sub-window should have approximately {count:d} messages"))
def then_check_sub_window_size(context, count):
    for w in context["sub_windows"]:
        assert w.size == count


@then(parsers.parse("an InvalidStepUnitError should be raised with unit \"{unit}\""))
def then_check_invalid_unit_error(context, unit):
    exc = context.get("exception")
    assert isinstance(exc, InvalidStepUnitError)
    assert exc.step_unit == unit


@then(parsers.parse("an InvalidSplitError should be raised with n={n:d}"))
def then_check_invalid_split_error(context, n):
    exc = context.get("exception")
    assert isinstance(exc, InvalidSplitError)
    assert exc.n == n


@then(parsers.parse("each window should span at most {hours:d} hours"))
def then_check_window_span(context, hours):
    max_duration = timedelta(hours=hours)
    for w in context["windows"]:
        duration = w.end_time - w.start_time
        assert duration <= max_duration + timedelta(seconds=1)


@then("the signatures should be identical")
def then_check_signatures_identical(context):
    assert context["signature"] == context["signature_2"]


@then(parsers.parse("if I change the template to \"{template}\" the signature should change"))
def then_check_signature_change(context, template):
    with patch("egregora.transformations.windowing.build_conversation_xml") as mock_build_xml:
        mock_build_xml.return_value = "<chat>content</chat>"
        sig3 = generate_window_signature(context["table"], context["config"], template)
        assert sig3 != context["signature"]
