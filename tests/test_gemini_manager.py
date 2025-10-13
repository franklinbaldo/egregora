import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from egregora.gemini_manager import GeminiManager, GeminiQuotaError


@pytest.fixture
def mock_gemini_client():
    """Fixture for a mocked Gemini client."""
    return MagicMock()


@pytest.fixture
def gemini_manager(mock_gemini_client):
    """Fixture for a GeminiManager instance with a mocked client."""
    return GeminiManager(client=mock_gemini_client)


class TestGeminiManager:
    @pytest.mark.asyncio
    async def test_generate_content_passes_safety_settings(self, gemini_manager, mock_gemini_client):
        """Test that generate_content correctly passes safety_settings."""
        mock_response = MagicMock()
        mock_gemini_client.models.generate_content = AsyncMock(return_value=mock_response)

        safety_settings = [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]

        await gemini_manager.generate_content(
            subsystem="test",
            model="gemini-pro",
            contents=[],
            config={},
            safety_settings=safety_settings,
        )

        mock_gemini_client.models.generate_content.assert_called_once()
        _, kwargs = mock_gemini_client.models.generate_content.call_args
        assert kwargs["safety_settings"] == safety_settings