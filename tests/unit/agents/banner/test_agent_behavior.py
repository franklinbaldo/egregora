from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.banner.agent import generate_banner


@pytest.fixture
def mock_provider(monkeypatch):
    """Mock GeminiImageGenerationProvider to control behavior."""
    mock = MagicMock()
    monkeypatch.setattr("egregora.agents.banner.agent.GeminiImageGenerationProvider", mock)
    return mock


@pytest.fixture
def mock_genai(monkeypatch):
    """Mock google.generativeai.GenerativeModel."""
    # We need to mock the GenerativeModel class in the agent module's namespace
    mock_model = MagicMock()
    # Since agent.py does `import google.generativeai as genai`
    # and uses `genai.GenerativeModel`, we need to patch `egregora.agents.banner.agent.genai.GenerativeModel`
    patcher = patch("egregora.agents.banner.agent.genai.GenerativeModel", return_value=mock_model)
    patcher.start()
    yield mock_model
    patcher.stop()


@pytest.fixture
def mock_availability(monkeypatch):
    monkeypatch.setattr("egregora.agents.banner.agent.is_banner_generation_available", lambda: True)


def test_generate_banner_handles_provider_error(mock_provider, mock_genai, mock_availability):
    """Test that generate_banner handles provider returning error."""
    _ = mock_genai
    _ = mock_availability
    # Arrange
    provider_instance = mock_provider.return_value
    provider_instance.generate.return_value = MagicMock(
        has_image=False, error="Specific Error", error_code="SPECIFIC_CODE"
    )

    # Act
    result = generate_banner("Title", "Summary")

    # Assert
    assert not result.success
    assert result.error == "Specific Error"
    assert result.error_code == "SPECIFIC_CODE"


def test_generate_banner_handles_provider_instantiation_error(mock_provider, mock_genai, mock_availability):
    """Test behavior when provider instantiation fails."""
    _ = mock_genai
    _ = mock_availability
    # Arrange
    mock_provider.side_effect = Exception("Init failed")

    # Act
    with pytest.raises(Exception, match="Init failed"):
        generate_banner("Title", "Summary")
