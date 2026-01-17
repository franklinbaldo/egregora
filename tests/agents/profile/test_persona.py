from unittest.mock import AsyncMock, patch

import pytest

from egregora.agents.profile.models import PersonaModel
from egregora.agents.profile.persona import extract_persona


@pytest.mark.asyncio
async def test_extract_persona_empty():
    persona = await extract_persona([], "Test User")
    assert persona.communication_style == "Unknown (No history)"


@pytest.mark.asyncio
async def test_extract_persona_mocked():
    mock_agent = AsyncMock()
    mock_result = AsyncMock()
    mock_result.output = PersonaModel(
        communication_style="Direct",
        core_values=["Efficiency"],
        argumentation_style="Data-driven",
        frequent_topics=["Python"],
        voice_sample="Use the vector DB.",
    )
    mock_agent.run.return_value = mock_result

    with patch("egregora.agents.profile.persona.create_persona_agent", return_value=mock_agent):
        persona = await extract_persona(["msg1", "msg2"], "Test User")
        assert persona.communication_style == "Direct"
        assert persona.core_values == ["Efficiency"]
