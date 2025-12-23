from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, create_autospec

import pytest
from datetime import datetime, UTC
from egregora.orchestration.runner import PipelineRunner
from egregora.orchestration.context import PipelineContext, PipelineConfig
from egregora.agents.writer import WindowProcessingParams

if TYPE_CHECKING:
    from egregora.transformations.windowing import Window

logger = logging.getLogger(__name__)

class TestPipelineRunner:
    """E2E tests for PipelineRunner."""

    @pytest.fixture
    def mock_context(self):
        """Mock PipelineContext with all necessary attributes."""
        mock_context = create_autospec(PipelineContext, instance=True)
        mock_context.config = MagicMock()
        mock_context.config.pipeline.max_windows = 1
        mock_context.config.pipeline.use_full_context_window = False
        mock_context.config.pipeline.max_prompt_tokens = 1000
        mock_context.config.enrichment.enabled = False
        mock_context.config.enrichment.max_enrichments = 0
        mock_context.config.enrichment.max_urls = 0
        mock_context.config.enrichment.max_concurrent_enrichments = 1
        mock_context.config.quota.concurrency = 1
        mock_context.config.rag.enabled = False

        mock_context.adapter = MagicMock()
        mock_context.output_format = MagicMock()
        mock_context.output_format.url_convention = MagicMock()
        mock_context.url_context = MagicMock()
        mock_context.cache = MagicMock()
        mock_context.config_obj = MagicMock()
        mock_context.config_obj.is_demo = False
        mock_context.run_id = None
        mock_context.task_store = MagicMock()
        mock_context.enrichment_cache = MagicMock()
        mock_context.site_root = MagicMock()
        mock_context.usage_tracker = MagicMock()

        return mock_context

    @pytest.fixture
    def mock_window(self):
        """Mock Window object."""
        mock_window = MagicMock()
        mock_window.size = 10
        mock_window.window_index = 0
        mock_window.start_time = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        mock_window.end_time = datetime(2023, 1, 1, 11, 0, tzinfo=UTC)
        mock_window.table = MagicMock() # Needs to be a table-like object if accessed

        # Mock window.table execution to return a list for extract_commands_list
        mock_result = MagicMock()
        mock_result.to_pylist.return_value = []
        mock_window.table.execute.return_value = mock_result
        mock_window.table.to_pylist.return_value = [] # Fallback

        return mock_window

    def test_runner_run_method(self, mock_context, mock_window):
        """Verify that the runner processes a single window correctly via run()."""

        # 3. Initialize Runner
        runner = PipelineRunner(mock_context)

        # 4. Run Process Windows
        # Mocking external calls
        with pytest.MonkeyPatch.context() as m:
            mock_write = Mock(return_value={"posts": ["post1"], "profiles": []})
            m.setattr("egregora.orchestration.runner.write_posts_for_window", mock_write)

            # Also mock PipelineFactory.create_writer_resources
            m.setattr("egregora.orchestration.factory.PipelineFactory.create_writer_resources", Mock())

            # Mock run_async_safely to just return the result of the callable
            m.setattr("egregora.orchestration.runner.run_async_safely", lambda x: x)

            # Mock process_media_for_window to return (table, {})
            m.setattr("egregora.orchestration.runner.process_media_for_window",
                      Mock(return_value=(mock_window.table, {})))

            # Mock filter_commands to return empty list
            m.setattr("egregora.orchestration.runner.filter_commands", Mock(return_value=[]))

            # Mock generate_profile_posts
            m.setattr("egregora.orchestration.runner.generate_profile_posts", Mock(return_value=[]))

            # Mock _perform_enrichment
            m.setattr(runner, "_perform_enrichment", Mock(return_value=mock_window.table))

            # Mock process_background_tasks
            m.setattr(runner, "process_background_tasks", Mock())

            # Mock _save_checkpoint
            mock_save_checkpoint = Mock()
            m.setattr(runner, "_save_checkpoint", mock_save_checkpoint)

            # Mock _record_run_start/completion
            mock_record_start = Mock()
            m.setattr(runner, "_record_run_start", mock_record_start)
            mock_record_completion = Mock()
            m.setattr(runner, "_record_run_completion", mock_record_completion)

            # Run the runner
            results = runner.run(
                windows_iterator=[mock_window],
                checkpoint_path=MagicMock(),
                enable_enrichment=False,
                embedding_model="test-model",
                run_store=MagicMock(),
            )

        # 5. Assertions
        assert len(results) == 1
        assert mock_write.called
        assert mock_save_checkpoint.called
        assert mock_record_start.called
        assert mock_record_completion.called
