from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from egregora.data_primitives.document import OutputSink
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.exceptions import MediaPersistenceError, ProfileGenerationError
from egregora.orchestration.runner import PipelineRunner


def test_runner_raises_specific_exceptions():
    """
    Verify that specific exceptions are raised instead of swallowed.
    """
    # Arrange
    context = MagicMock(spec=PipelineContext)
    output_sink = MagicMock(spec=OutputSink)
    context.output_sink = output_sink
    context.config.pipeline.is_demo = False
    context.enable_enrichment = False
    context.url_context = None

    runner = PipelineRunner(context)

    window = MagicMock()
    window.start_time = datetime(2023, 1, 1, 10, 0)
    window.end_time = datetime(2023, 1, 1, 11, 0)
    window.size = 10

    runner._extract_adapter_info = MagicMock(return_value=("", ""))

    # 1. Verify Profile Generation Error
    with (
        patch("egregora.orchestration.runner.process_media_for_window") as mock_media,
        patch("egregora.orchestration.runner.generate_profile_posts") as mock_profile,
        patch("egregora.orchestration.runner.write_posts_for_window") as mock_write,
    ):
        mock_media.return_value = (MagicMock(), {})
        mock_write.return_value = {"posts": [], "profiles": []}

        # Make generate_profile_posts raise a generic exception
        mock_profile.side_effect = ValueError("Profile Generation Failed!")

        with pytest.raises(ProfileGenerationError) as excinfo:
            runner._process_single_window(window, depth=0)

        assert "Failed to generate profile posts" in str(excinfo.value)
        assert "Profile Generation Failed!" in str(excinfo.value)

    # 2. Verify Media Persistence Error
    # Reset side effect on persist from previous run (mock object persists across loop iterations if not careful)
    output_sink.persist.side_effect = OSError("Disk Full!")

    with (
        patch("egregora.orchestration.runner.process_media_for_window") as mock_media,
        patch("egregora.orchestration.runner.generate_profile_posts") as mock_profile,
        patch("egregora.orchestration.runner.write_posts_for_window") as mock_write,
    ):
        mock_media.return_value = (MagicMock(), {"file.jpg": MagicMock()})
        mock_write.return_value = {"posts": [], "profiles": []}
        # Explicitly set enable_enrichment false to trigger media persistence block
        context.enable_enrichment = False

        with pytest.raises(MediaPersistenceError) as excinfo:
            runner._process_single_window(window, depth=0)

        assert "Failed to write media file" in str(excinfo.value)
        assert "Disk Full!" in str(excinfo.value)
