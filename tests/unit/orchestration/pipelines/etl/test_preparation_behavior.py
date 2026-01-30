"""Behavioral tests for preparation.py."""

import logging
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from egregora.orchestration.pipelines.etl.preparation import (
    Conversation,
    FilterOptions,
    PreparedPipelineData,
    _apply_date_filters,
    _apply_filters,
    _calculate_max_window_size,
    _extract_adapter_info,
    _parse_and_validate_source,
    _setup_content_directories,
    get_pending_conversations,
    prepare_pipeline_data,
    validate_dates,
    validate_timezone_arg,
)


class TestValidators:
    """Tests for CLI argument validators."""

    def test_validate_dates_valid(self):
        """Test parsing of valid date strings."""
        f, t = validate_dates("2023-01-01", "2023-12-31")
        assert f == date(2023, 1, 1)
        assert t == date(2023, 12, 31)

    def test_validate_dates_empty(self):
        """Test behavior with empty inputs."""
        f, t = validate_dates(None, None)
        assert f is None
        assert t is None

    def test_validate_dates_invalid_format(self, capsys):
        """Test that invalid date formats cause SystemExit."""
        with pytest.raises(SystemExit):
            validate_dates("invalid-date", None)
        # Check stderr/stdout if needed, but SystemExit is the contract

    def test_validate_timezone_valid(self, capsys):
        """Test valid timezone."""
        # Assuming UTC is always valid
        validate_timezone_arg("UTC")
        captured = capsys.readouterr()
        assert "Using timezone: UTC" in captured.out

    def test_validate_timezone_invalid(self):
        """Test invalid timezone raises SystemExit."""
        with pytest.raises(SystemExit):
            validate_timezone_arg("Invalid/Timezone")


class TestFilters:
    """Tests for filter application logic."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock Ibis table."""
        table = MagicMock()
        # Mock count().execute() to return an integer
        table.count.return_value.execute.return_value = 100

        # Configure date() mock to support comparisons
        date_col = MagicMock()
        date_col.__ge__.return_value = MagicMock()
        date_col.__le__.return_value = MagicMock()
        table.ts.date.return_value = date_col

        # Configure filter() return value to also have integer count
        table.filter.return_value.count.return_value.execute.return_value = 100

        return table

    def test_apply_date_filters_no_dates(self, mock_table):
        """Test that no filtering happens when dates are missing."""
        result = _apply_date_filters(mock_table, None, None)
        assert result is mock_table
        # Should not call filter
        mock_table.filter.assert_not_called()

    def test_apply_date_filters_from_date(self, mock_table):
        """Test filtering with from_date only."""
        mock_table.filter.return_value.count.return_value.execute.return_value = 80
        from_d = date(2023, 1, 1)

        result = _apply_date_filters(mock_table, from_d, None)

        assert result is mock_table.filter.return_value
        # Verify filter was called
        mock_table.filter.assert_called_once()
        # We can't easily verify the expression object equality, but we know it was called

    def test_apply_date_filters_to_date(self, mock_table):
        """Test filtering with to_date only."""
        mock_table.filter.return_value.count.return_value.execute.return_value = 80
        to_d = date(2023, 12, 31)

        result = _apply_date_filters(mock_table, None, to_d)

        assert result is mock_table.filter.return_value
        mock_table.filter.assert_called_once()

    def test_apply_date_filters_both(self, mock_table):
        """Test filtering with both dates."""
        mock_table.filter.return_value.count.return_value.execute.return_value = 50
        from_d = date(2023, 1, 1)
        to_d = date(2023, 1, 31)

        result = _apply_date_filters(mock_table, from_d, to_d)

        assert result is mock_table.filter.return_value
        mock_table.filter.assert_called_once()

    @patch("egregora.orchestration.pipelines.etl.preparation.filter_egregora_messages")
    @patch("egregora.orchestration.pipelines.etl.preparation.filter_opted_out_authors")
    def test_apply_filters_orchestration(self, mock_opt_out, mock_egregora, mock_table):
        """Test that _apply_filters coordinates all filter steps."""
        ctx = MagicMock()
        options = FilterOptions(from_date=date(2023, 1, 1))

        # Setup chain
        mock_egregora.return_value = (mock_table, 10) # table, removed
        mock_opt_out.return_value = (mock_table, 5) # table, removed

        result = _apply_filters(mock_table, ctx, options)

        mock_egregora.assert_called_once()
        mock_opt_out.assert_called_once()
        # _apply_date_filters logic is embedded, verify table.filter called
        mock_table.filter.assert_called()


class TestDirectorySetup:
    """Tests for directory creation and validation."""

    def test_setup_directories_valid(self):
        """Test valid directory structure creation."""
        ctx = MagicMock()
        root = Path("/tmp/site")
        docs = root / "docs"

        ctx.site_root = root
        ctx.docs_dir = docs
        ctx.posts_dir = docs / "posts"
        ctx.profiles_dir = docs / "profiles"
        ctx.media_dir = docs / "media"

        # Mock relative_to to pass
        # Since we are using real Path objects in mock if possible,
        # or we mock the Path objects on the context.
        # Let's mock the Path objects to track mkdir calls

        # Resetting to Mocks for behavior verification
        ctx.posts_dir = MagicMock(spec=Path)
        ctx.profiles_dir = MagicMock(spec=Path)
        ctx.media_dir = MagicMock(spec=Path)

        # Setup relative_to to return successfully
        ctx.posts_dir.relative_to.return_value = ctx.posts_dir
        ctx.profiles_dir.relative_to.return_value = ctx.profiles_dir
        ctx.media_dir.relative_to.return_value = ctx.media_dir

        _setup_content_directories(ctx)

        ctx.posts_dir.mkdir.assert_called_with(parents=True, exist_ok=True)
        ctx.profiles_dir.mkdir.assert_called_with(parents=True, exist_ok=True)
        ctx.media_dir.mkdir.assert_called_with(parents=True, exist_ok=True)

    def test_setup_directories_traversal_posts(self):
        """Test error when posts dir is outside docs dir."""
        ctx = MagicMock()
        ctx.docs_dir = Path("/safe/docs")
        ctx.posts_dir = MagicMock(spec=Path)
        ctx.posts_dir.relative_to.side_effect = ValueError("Not relative")
        ctx.posts_dir.__str__.return_value = "/unsafe/posts"

        with pytest.raises(ValueError, match="must reside inside the MkDocs docs_dir"):
            _setup_content_directories(ctx)

    def test_setup_directories_media_fallback(self):
        """Test media dir can be in site root if not in docs dir."""
        ctx = MagicMock()
        ctx.docs_dir = Path("/site/docs")
        ctx.site_root = Path("/site")

        ctx.posts_dir = MagicMock() # Assume valid
        ctx.profiles_dir = MagicMock() # Assume valid

        ctx.media_dir = MagicMock(spec=Path)
        # First check fails (not in docs)
        ctx.media_dir.relative_to.side_effect = [ValueError, MagicMock()]

        _setup_content_directories(ctx)

        # Should have tried twice
        assert ctx.media_dir.relative_to.call_count == 2
        ctx.media_dir.mkdir.assert_called()


class TestAdapterInfo:
    """Tests for extracting adapter metadata."""

    def test_extract_info_attributes(self):
        """Test extraction from static attributes."""
        ctx = MagicMock()
        ctx.adapter.content_summary = "Summary"
        ctx.adapter.generation_instructions = "Instructions"

        summary, instructions = _extract_adapter_info(ctx)

        assert summary == "Summary"
        assert instructions == "Instructions"

    def test_extract_info_callables(self):
        """Test extraction from callable attributes."""
        ctx = MagicMock()
        ctx.adapter.content_summary = lambda: "Dynamic Summary"
        ctx.adapter.generation_instructions = lambda: "Dynamic Instructions"

        summary, instructions = _extract_adapter_info(ctx)

        assert summary == "Dynamic Summary"
        assert instructions == "Dynamic Instructions"

    def test_extract_info_missing(self):
        """Test graceful handling of missing attributes."""
        ctx = MagicMock()
        del ctx.adapter.content_summary
        del ctx.adapter.generation_instructions
        # Actually MagicMock creates them by default, so we need to ensure they raise AttributeError
        # or rely on default MagicMock behavior which is returning a Mock (truthy).
        # The code checks `getattr(adapter, "content_summary", "")`.
        # If we use a real object or spec=InputAdapter it might be better.
        # But let's force it.

        ctx.adapter = Mock(spec=[]) # Empty spec

        summary, instructions = _extract_adapter_info(ctx)
        assert summary == ""
        assert instructions == ""

    def test_extract_info_errors(self, caplog):
        """Test graceful handling of exceptions during extraction."""
        ctx = MagicMock()
        ctx.adapter.content_summary = Mock(side_effect=TypeError("Error"))

        with caplog.at_level(logging.DEBUG):
            summary, instructions = _extract_adapter_info(ctx)

        assert summary == ""
        assert "failed to provide content_summary" in caplog.text


class TestPipelinePreparation:
    """Tests for top-level pipeline preparation flow."""

    @patch("egregora.orchestration.pipelines.etl.preparation.create_and_initialize_adapter")
    @patch("egregora.orchestration.pipelines.etl.preparation._parse_and_validate_source")
    @patch("egregora.orchestration.pipelines.etl.preparation._setup_content_directories")
    @patch("egregora.orchestration.pipelines.etl.preparation._process_commands_and_avatars")
    @patch("egregora.orchestration.pipelines.etl.preparation._apply_filters")
    @patch("egregora.orchestration.pipelines.etl.preparation.create_windows")
    @patch("egregora.orchestration.pipelines.etl.preparation.index_documents")
    @patch("egregora.orchestration.pipelines.etl.preparation.reset_backend")
    def test_prepare_pipeline_data_happy_path(
        self,
        mock_reset,
        mock_index,
        mock_create_windows,
        mock_apply_filters,
        mock_process_cmds,
        mock_setup_dirs,
        mock_parse,
        mock_create_adapter,
    ):
        """Test the happy path of prepare_pipeline_data."""
        adapter = MagicMock()
        ctx = MagicMock()
        ctx.config.rag.enabled = True
        ctx.output_dir = Path("/out")

        run_params = MagicMock()
        run_params.config.pipeline.timezone = "UTC"
        run_params.config.pipeline.max_window_time = None
        run_params.config.pipeline.from_date = None
        run_params.config.pipeline.to_date = None
        run_params.config.enrichment.enabled = True

        # Setup mocks
        mock_sink = MagicMock()
        mock_sink.documents.return_value = ["doc1"]
        mock_create_adapter.return_value = mock_sink

        mock_table = MagicMock()
        mock_parse.return_value = mock_table
        mock_process_cmds.return_value = mock_table
        mock_apply_filters.return_value = mock_table

        mock_create_windows.return_value = iter([])

        # Execute
        data = prepare_pipeline_data(adapter, run_params, ctx)

        # Assertions
        assert isinstance(data, PreparedPipelineData)
        assert data.messages_table == mock_table
        assert data.enable_enrichment is True

        mock_create_adapter.assert_called_once()
        mock_parse.assert_called_once()
        mock_setup_dirs.assert_called_once()
        mock_process_cmds.assert_called_once()
        mock_apply_filters.assert_called_once()
        mock_create_windows.assert_called_once()
        mock_index.assert_called_once()
        mock_reset.assert_called_once()

    @patch("egregora.orchestration.pipelines.etl.preparation.create_and_initialize_adapter")
    @patch("egregora.orchestration.pipelines.etl.preparation._parse_and_validate_source")
    @patch("egregora.orchestration.pipelines.etl.preparation._setup_content_directories")
    @patch("egregora.orchestration.pipelines.etl.preparation._process_commands_and_avatars")
    @patch("egregora.orchestration.pipelines.etl.preparation._apply_filters")
    @patch("egregora.orchestration.pipelines.etl.preparation.create_windows")
    def test_prepare_pipeline_data_no_enrichment_with_dates(
        self,
        mock_create_windows,
        mock_apply_filters,
        mock_process_cmds,
        mock_setup_dirs,
        mock_parse,
        mock_create_adapter,
    ):
        """Test prepare_pipeline_data with enrichment disabled and dates present."""
        adapter = MagicMock()
        ctx = MagicMock()
        ctx.config.rag.enabled = False # Disable RAG

        run_params = MagicMock()
        run_params.config.pipeline.timezone = "UTC"
        run_params.config.pipeline.max_window_time = None
        run_params.config.pipeline.from_date = "2023-01-01"
        run_params.config.pipeline.to_date = "2023-12-31"
        run_params.config.enrichment.enabled = False

        mock_sink = MagicMock()
        mock_create_adapter.return_value = mock_sink
        mock_sink.documents.return_value = [] # No docs to index

        mock_table = MagicMock()
        mock_parse.return_value = mock_table
        mock_process_cmds.return_value = mock_table
        mock_apply_filters.return_value = mock_table

        mock_create_windows.return_value = iter([])

        data = prepare_pipeline_data(adapter, run_params, ctx)

        assert data.enable_enrichment is False
        # Verify date parsing happened (implicit in _apply_filters call, but we can check if it didn't crash)
        mock_apply_filters.assert_called_once()
        # Verify RAG indexing not called (implicit by mocks not being patched/called)

        # Verify FilterOptions passed to _apply_filters has dates
        args, _ = mock_apply_filters.call_args
        options = args[2] # 3rd arg
        assert isinstance(options, FilterOptions)
        assert options.from_date == date(2023, 1, 1)
        assert options.to_date == date(2023, 12, 31)

    def test_parse_and_validate_source(self):
        """Test source parsing and metadata logging."""
        adapter = MagicMock()
        adapter.source_name = "test_source"
        adapter.get_metadata.return_value = {"group_name": "Test Group"}

        # Mock table count
        mock_table = MagicMock()
        mock_table.count.return_value.execute.return_value = 42
        adapter.parse.return_value = mock_table

        result = _parse_and_validate_source(
            adapter, Path("input.zip"), "UTC", output_adapter=None
        )

        assert result == mock_table
        adapter.parse.assert_called_with(Path("input.zip"), timezone="UTC", output_adapter=None)
        adapter.get_metadata.assert_called()


class TestWindowProcessing:
    """Tests for window splitting and processing logic."""

    def test_calculate_max_window_size(self):
        """Test max window size calculation."""
        config = MagicMock()
        config.pipeline.use_full_context_window = False
        config.pipeline.max_prompt_tokens = 1000

        # 1000 * 0.8 / 5 = 160
        size = _calculate_max_window_size(config)
        assert size == 160

    @patch("egregora.orchestration.pipelines.etl.preparation.process_media_for_window")
    @patch("egregora.orchestration.pipelines.etl.preparation.perform_enrichment")
    def test_get_pending_conversations_flow(self, mock_enrich, mock_media):
        """Test the main generator flow."""
        # Setup
        ctx = MagicMock()
        ctx.config.pipeline.max_windows = None

        # Setup Window
        window = MagicMock()
        window.size = 100
        window.window_index = 0
        window.table = MagicMock()

        dataset = PreparedPipelineData(
            messages_table=MagicMock(),
            windows_iterator=iter([window]),
            checkpoint_path=Path("ckpt"),
            context=ctx,
            enable_enrichment=True,
            embedding_model="model"
        )

        # Mock media return
        mock_media.return_value = (MagicMock(), {}) # table, mapping

        # Execute
        conversations = list(get_pending_conversations(dataset))

        assert len(conversations) == 1
        assert conversations[0].window == window
        assert conversations[0].depth == 0

        mock_media.assert_called_once()
        mock_enrich.assert_called_once()

    @patch("egregora.orchestration.pipelines.etl.preparation.split_window_into_n_parts")
    @patch("egregora.orchestration.pipelines.etl.preparation.perform_enrichment")
    @patch("egregora.orchestration.pipelines.etl.preparation.process_media_for_window")
    def test_get_pending_conversations_splitting(self, mock_media, mock_enrich, mock_split):
        """Test that large windows are split."""
        ctx = MagicMock()
        ctx.config.pipeline.max_windows = None
        ctx.config.pipeline.use_full_context_window = False
        # Set small max size to force split
        ctx.config.pipeline.max_prompt_tokens = 100
        # _calculate_max_window_size -> 100 * 0.8 / 5 = 16

        large_window = MagicMock()
        large_window.size = 20 # > 16

        small_window_1 = MagicMock()
        small_window_1.size = 10
        small_window_2 = MagicMock()
        small_window_2.size = 10

        mock_split.return_value = [small_window_1, small_window_2]

        dataset = PreparedPipelineData(
            messages_table=MagicMock(),
            windows_iterator=iter([large_window]),
            checkpoint_path=Path("ckpt"),
            context=ctx,
            enable_enrichment=True,
            embedding_model="model"
        )

        # Mocks for processing
        mock_media.return_value = (MagicMock(), {})

        conversations = list(get_pending_conversations(dataset))

        # Should get 2 conversations, not 1
        assert len(conversations) == 2
        assert conversations[0].window == small_window_1
        assert conversations[0].depth == 1
        assert conversations[1].window == small_window_2
        assert conversations[1].depth == 1

        mock_split.assert_called_once()
