import logging
from unittest.mock import patch

import pytest

from egregora.agents.banner.agent import generate_banner


@patch("egregora.agents.banner.agent.genai.Client")
@patch("egregora.agents.banner.agent._generate_banner_image", side_effect=ValueError("Unexpected test error"))
def test_generate_banner_propagates_unexpected_error(mock_generate, mock_client, caplog):
    """
    Given an unexpected error occurs inside the banner generation logic
    When the generate_banner function is called
    Then the original exception should be propagated
    And the generic "unexpected error" message should NOT be logged.
    """
    # Arrange
    # Mocks are set up via decorators.

    # Act & Assert
    # We expect the ValueError to be raised from our mock.
    with pytest.raises(ValueError, match="Unexpected test error"):
        with caplog.at_level(logging.ERROR):
            generate_banner("A Title", "A summary")

    # Before refactoring, the `except Exception` block will catch the ValueError,
    # log the "unexpected error" message, and then re-raise. This will cause
    # the assertion below to fail.
    # After refactoring (removing the block), the error will propagate directly,
    # and the unwanted log message will not be present, allowing this test to pass.
    assert "An unexpected error occurred during banner generation" not in caplog.text
