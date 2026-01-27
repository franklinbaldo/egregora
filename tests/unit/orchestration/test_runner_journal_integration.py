from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from egregora.orchestration.context import PipelineContext
from egregora.orchestration.exceptions import OutputSinkError
from egregora.orchestration.runner import PipelineRunner


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=PipelineContext)
    ctx.config = MagicMock()
    ctx.config.pipeline.max_prompt_tokens = 1000
    ctx.config.models.writer = "gpt-4"
    ctx.config.enrichment.enabled = False  # Disable enrichment to simplify mocks
    ctx.site_root = None
    ctx.run_id = uuid4()
    ctx.output_sink = MagicMock()
    ctx.adapter = MagicMock()
    # Ensure enrichment property mirrors config
    ctx.enable_enrichment = False
    return ctx


@pytest.fixture
def mock_window():
    window = MagicMock()
    window.start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    window.end_time = datetime(2023, 1, 1, 13, 0, 0, tzinfo=UTC)
    window.size = 10
    window.table = MagicMock()
    return window


class TestPipelineRunnerJournalIntegration:
    @patch("egregora.orchestration.runner.generate_window_signature")
    @patch("egregora.orchestration.runner.PromptManager")
    @patch("egregora.orchestration.runner.window_already_processed")
    def test_process_window_skipped_if_already_processed(
        self, mock_check, mock_pm, mock_sig, mock_context, mock_window
    ):
        """Test that window processing is skipped if journal exists."""
        runner = PipelineRunner(mock_context)

        # Setup mocks
        mock_pm.get_template_content.return_value = "template"
        mock_sig.return_value = "existing-signature"
        mock_check.return_value = True  # Simulate already processed

        # Execute
        result = runner._process_single_window(mock_window)

        # Verify
        assert result == {}
        mock_check.assert_called_once_with(mock_context.output_sink, "existing-signature")
        # Ensure heavy operations were skipped
        mock_context.output_sink.persist.assert_not_called()

    @patch("egregora.orchestration.runner.generate_window_signature")
    @patch("egregora.orchestration.runner.PromptManager")
    @patch("egregora.orchestration.runner.window_already_processed")
    @patch("egregora.orchestration.runner.process_media_for_window")
    @patch("egregora.orchestration.runner.write_posts_for_window")
    @patch("egregora.orchestration.runner.generate_profile_posts")
    @patch("egregora.orchestration.runner.create_journal_document")
    @patch("egregora.orchestration.runner.WriterResources")
    def test_process_window_creates_journal_on_success(
        self,
        mock_resources_cls,
        mock_create_journal,
        mock_gen_profiles,
        mock_write_posts,
        mock_media,
        mock_check,
        mock_pm,
        mock_sig,
        mock_context,
        mock_window,
    ):
        """Test that journal is created and persisted after successful processing."""
        runner = PipelineRunner(mock_context)

        # Setup mocks
        mock_pm.get_template_content.return_value = "template"
        mock_sig.return_value = "new-signature"
        mock_check.return_value = False  # Not processed yet

        mock_resources_cls.from_pipeline_context.return_value = MagicMock()

        # Mock processing returns
        mock_media.return_value = (MagicMock(), {})
        mock_write_posts.return_value = {"posts": ["post1"], "profiles": ["profile1"]}
        mock_gen_profiles.return_value = []

        mock_journal_doc = MagicMock()
        mock_create_journal.return_value = mock_journal_doc

        # Execute
        result = runner._process_single_window(mock_window)

        # Verify
        assert "post1" in result[next(iter(result.keys()))]["posts"]

        # Check journal creation
        mock_create_journal.assert_called_once_with(
            signature="new-signature",
            run_id=mock_context.run_id,
            window_start=mock_window.start_time,
            window_end=mock_window.end_time,
            model="gpt-4",
            posts_generated=1,  # 1 post generated (minus 0 scheduled)
            profiles_updated=1,  # 1 profile generated
        )

        # Check persistence
        # persist is called for posts/profiles/announcements too, so we check if journal was passed
        mock_context.output_sink.persist.assert_any_call(mock_journal_doc)

    @patch("egregora.orchestration.runner.generate_window_signature")
    @patch("egregora.orchestration.runner.PromptManager")
    @patch("egregora.orchestration.runner.window_already_processed")
    def test_process_window_raises_sink_error(self, mock_check, mock_pm, mock_sig, mock_context, mock_window):
        runner = PipelineRunner(mock_context)
        mock_context.output_sink = None

        with pytest.raises(OutputSinkError):
            runner._process_single_window(mock_window)

    @patch("egregora.orchestration.runner.generate_window_signature")
    @patch("egregora.orchestration.runner.PromptManager")
    @patch("egregora.orchestration.runner.window_already_processed")
    @patch("egregora.orchestration.runner.process_media_for_window")
    @patch("egregora.orchestration.runner.write_posts_for_window")
    @patch("egregora.orchestration.runner.generate_profile_posts")
    @patch("egregora.orchestration.runner.create_journal_document")
    @patch("egregora.orchestration.runner.WriterResources")
    def test_process_window_handles_journal_persist_error(
        self,
        mock_resources_cls,
        mock_create_journal,
        mock_gen_profiles,
        mock_write_posts,
        mock_media,
        mock_check,
        mock_pm,
        mock_sig,
        mock_context,
        mock_window,
    ):
        """Test that pipeline continues if journal persistence fails."""
        runner = PipelineRunner(mock_context)

        # Setup mocks
        mock_pm.get_template_content.return_value = "template"
        mock_sig.return_value = "new-signature"
        mock_check.return_value = False

        mock_resources_cls.from_pipeline_context.return_value = MagicMock()

        mock_media.return_value = (MagicMock(), {})
        mock_write_posts.return_value = {"posts": ["post1"], "profiles": []}
        mock_gen_profiles.return_value = []

        mock_journal_doc = MagicMock()
        mock_create_journal.return_value = mock_journal_doc

        # Configure output_sink.persist to raise error ONLY for journal
        def persist_side_effect(doc):
            if doc == mock_journal_doc:
                msg = "DB Error"
                raise Exception(msg)

        mock_context.output_sink.persist.side_effect = persist_side_effect

        # Execute
        result = runner._process_single_window(mock_window)

        # Verify pipeline succeeded (returned posts)
        assert "post1" in result[next(iter(result.keys()))]["posts"]

        # Verify persist was attempted
        mock_context.output_sink.persist.assert_any_call(mock_journal_doc)
