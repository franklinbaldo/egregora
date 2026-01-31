from __future__ import annotations

import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import ibis
from egregora.orchestration.pipelines.etl import preparation
from egregora.orchestration.pipelines.etl.preparation import (
    validate_dates,
    validate_timezone_arg,
    _setup_content_directories,
    _apply_date_filters,
    get_pending_conversations,
    FilterOptions,
    PreparedPipelineData,
)
from egregora.orchestration.context import PipelineContext
from egregora.transformations import Window
from egregora.config.exceptions import InvalidDateFormatError, InvalidTimezoneError

# --- Date Validation Tests ---

def test_validate_dates_valid():
    """Verify that valid date strings are parsed correctly."""
    with patch("egregora.orchestration.pipelines.etl.preparation.parse_date_arg") as mock_parse:
        mock_parse.side_effect = [date(2023, 1, 1), date(2023, 1, 31)]
        from_d, to_d = validate_dates("2023-01-01", "2023-01-31")
        assert from_d == date(2023, 1, 1)
        assert to_d == date(2023, 1, 31)

def test_validate_dates_invalid():
    """Verify that invalid date strings cause a SystemExit."""
    with patch("egregora.orchestration.pipelines.etl.preparation.parse_date_arg") as mock_parse:
        mock_parse.side_effect = InvalidDateFormatError("Invalid date")
        with pytest.raises(SystemExit) as exc:
            validate_dates("invalid", None)
        assert exc.value.code == 1

def test_validate_timezone_arg_valid():
    """Verify valid timezone passes."""
    with patch("egregora.orchestration.pipelines.etl.preparation.validate_timezone") as mock_val:
        validate_timezone_arg("UTC")
        mock_val.assert_called_with("UTC")

def test_validate_timezone_arg_invalid():
    """Verify invalid timezone causes SystemExit."""
    with patch("egregora.orchestration.pipelines.etl.preparation.validate_timezone") as mock_val:
        mock_val.side_effect = InvalidTimezoneError("Invalid TZ", ValueError("oops"))
        with pytest.raises(SystemExit) as exc:
            validate_timezone_arg("Invalid/Zone")
        assert exc.value.code == 1

# --- Directory Setup Tests ---

def test_setup_content_directories_success(tmp_path):
    """Verify directories are created correctly inside docs_dir."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    ctx = MagicMock(spec=PipelineContext)
    ctx.docs_dir = docs_dir
    ctx.posts_dir = docs_dir / "posts"
    ctx.profiles_dir = docs_dir / "profiles"
    ctx.media_dir = docs_dir / "media"

    _setup_content_directories(ctx)

    assert ctx.posts_dir.exists()
    assert ctx.profiles_dir.exists()
    assert ctx.media_dir.exists()

def test_setup_content_directories_traversal_error(tmp_path):
    """Verify ValueError is raised if directories are outside docs_dir."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    outside_dir = tmp_path / "outside"

    ctx = MagicMock(spec=PipelineContext)
    ctx.docs_dir = docs_dir
    ctx.posts_dir = outside_dir  # Invalid
    ctx.profiles_dir = docs_dir / "profiles"
    ctx.media_dir = docs_dir / "media"

    with pytest.raises(ValueError, match="must reside inside the MkDocs docs_dir"):
        _setup_content_directories(ctx)

def test_setup_content_directories_media_in_site_root(tmp_path):
    """Verify media directory can be in site_root if not in docs_dir."""
    docs_dir = tmp_path / "docs"
    site_root = tmp_path
    docs_dir.mkdir()

    ctx = MagicMock(spec=PipelineContext)
    ctx.docs_dir = docs_dir
    ctx.site_root = site_root
    ctx.posts_dir = docs_dir / "posts"
    ctx.profiles_dir = docs_dir / "profiles"
    ctx.media_dir = site_root / "media"  # Valid for media

    _setup_content_directories(ctx)
    assert ctx.media_dir.exists()

# --- Filtering Tests (using Ibis) ---

@pytest.fixture
def message_table():
    """Create a temporary Ibis table for testing."""
    con = ibis.duckdb.connect(":memory:")
    data = [
        {"ts": datetime(2023, 1, 1, 10, 0)},
        {"ts": datetime(2023, 1, 15, 10, 0)},
        {"ts": datetime(2023, 1, 31, 10, 0)},
    ]
    return con.create_table("messages", data)

def test_apply_date_filters_range(message_table):
    """Verify filtering by date range."""
    filtered = _apply_date_filters(
        message_table,
        from_date=date(2023, 1, 10),
        to_date=date(2023, 1, 20)
    )
    result = filtered.execute()
    assert len(result) == 1
    assert result.iloc[0]["ts"].day == 15

def test_apply_date_filters_from_only(message_table):
    """Verify filtering from a date."""
    filtered = _apply_date_filters(
        message_table,
        from_date=date(2023, 1, 15),
        to_date=None
    )
    result = filtered.execute()
    assert len(result) == 2  # 15th and 31st

def test_apply_date_filters_to_only(message_table):
    """Verify filtering up to a date."""
    filtered = _apply_date_filters(
        message_table,
        from_date=None,
        to_date=date(2023, 1, 15)
    )
    result = filtered.execute()
    assert len(result) == 2  # 1st and 15th

def test_apply_date_filters_none(message_table):
    """Verify no filtering happens if dates are None."""
    filtered = _apply_date_filters(
        message_table,
        from_date=None,
        to_date=None
    )
    result = filtered.execute()
    assert len(result) == 3

# --- Splitting Tests ---

@patch("egregora.orchestration.pipelines.etl.preparation.process_media_for_window")
@patch("egregora.orchestration.pipelines.etl.preparation.split_window_into_n_parts")
@patch("egregora.orchestration.pipelines.etl.preparation._calculate_max_window_size")
def test_get_pending_conversations_splitting(
    mock_calc_size,
    mock_split,
    mock_process_media,
):
    """Verify that large windows are split and re-queued."""
    # Setup
    mock_calc_size.return_value = 100

    # Create two windows: one small, one large
    small_window = MagicMock(spec=Window)
    small_window.size = 50
    small_window.window_index = 0
    small_window.table = MagicMock()

    large_window = MagicMock(spec=Window)
    large_window.size = 200
    large_window.window_index = 1
    large_window.table = MagicMock()

    # Split result for large window
    split_part1 = MagicMock(spec=Window)
    split_part1.size = 100
    split_part1.table = MagicMock()
    split_part1.window_index = 0
    split_part2 = MagicMock(spec=Window)
    split_part2.size = 100
    split_part2.table = MagicMock()
    split_part2.window_index = 0
    mock_split.return_value = [split_part1, split_part2]

    # Mock dataset
    ctx = MagicMock(spec=PipelineContext)
    ctx.config.pipeline.max_windows = None
    ctx.url_context = None
    ctx.output_sink.url_convention = "simple"

    dataset = MagicMock(spec=PreparedPipelineData)
    dataset.context = ctx
    dataset.windows_iterator = iter([large_window, small_window]) # Order: Large first to test re-queueing logic
    dataset.enable_enrichment = False

    # Mock media processing
    mock_process_media.return_value = (MagicMock(), {}) # table, media_mapping

    # Execute
    conversations = list(get_pending_conversations(dataset))

    # Assertions
    # 1. Split was called for large window
    mock_split.assert_called_once()

    # 2. We should have 3 conversations: split_part1, split_part2, small_window
    assert len(conversations) == 3

    # 3. Check order (reversed when extending left means they come out in order 1, 2)
    # The logic is: pop large -> split -> extendleft(reversed([p1, p2])) -> extendleft([p2, p1]) -> queue is [p1, p2, small]
    # So we expect p1, p2, small
    assert conversations[0].window == split_part1
    assert conversations[1].window == split_part2
    assert conversations[2].window == small_window

    # 4. Check depths
    assert conversations[0].depth == 1
    assert conversations[1].depth == 1
    assert conversations[2].depth == 0
