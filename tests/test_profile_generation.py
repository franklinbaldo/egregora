"""Tests for PROFILE post generation.

TDD: Profile generation from author's full message history.
- One PROFILE post per author per window
- LLM analyzes full author history, decides content
- Egregora authorship
"""

from unittest.mock import Mock, patch

import pytest

from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import DocumentType


class TestProfileMetadata:
    """Test PROFILE document metadata structure."""

    def test_profile_has_egregora_author(self):
        """PROFILE posts authored by Egregora."""
        from egregora.data_primitives.document import Document

        profile = Document(
            content="# John's Contributions\n\nJohn has...",
            type=DocumentType.PROFILE,
            metadata={
                "title": "John Doe: Key Contributions",
                "slug": "2025-03-07-john-contributions",
                "authors": [{"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}],
                "subject": "john-uuid",
                "date": "2025-03-07",
            },
        )

        assert profile.metadata["authors"][0]["uuid"] == EGREGORA_UUID
        assert profile.metadata["authors"][0]["name"] == EGREGORA_NAME

    def test_profile_has_subject(self):
        """PROFILE must have 'subject' (who it's about)."""
        from egregora.data_primitives.document import Document

        profile = Document(
            content="Analysis",
            type=DocumentType.PROFILE,
            metadata={
                "slug": "test",
                "authors": [{"uuid": EGREGORA_UUID}],
                "subject": "alice-uuid",  # Required!
            },
        )

        assert "subject" in profile.metadata
        assert profile.metadata["subject"] == "alice-uuid"


class TestProfileGeneration:
    """Test profile post generation logic."""

    @pytest.mark.asyncio
    async def test_generate_one_profile_per_author(self):
        """Generate ONE profile post per active author in window."""
        from egregora.agents.profile.generator import generate_profile_posts

        # Mock context
        ctx = Mock()
        ctx.config = Mock()
        ctx.config.models = Mock()
        ctx.config.models.writer = "gemini-2.0-flash"

        # Mock messages from 2 authors
        messages = [
            {"author_uuid": "john-uuid", "author_name": "John", "text": "Message 1"},
            {"author_uuid": "john-uuid", "author_name": "John", "text": "Message 2"},
            {"author_uuid": "alice-uuid", "author_name": "Alice", "text": "Message 3"},
        ]

        # Generate profiles
        with patch("egregora.agents.profile.generator._generate_profile_content") as mock_gen:
            mock_gen.return_value = "# Profile content"

            profiles = await generate_profile_posts(ctx=ctx, messages=messages, window_date="2025-03-07")

        # Should create 2 profiles (one per author)
        assert len(profiles) == 2

        # All should be PROFILE type
        assert all(p.type == DocumentType.PROFILE for p in profiles)

        # All authored by Egregora
        assert all(p.metadata["authors"][0]["uuid"] == EGREGORA_UUID for p in profiles)

    @pytest.mark.asyncio
    async def test_profile_analyzes_full_history(self):
        """Profile generation receives ALL messages from author."""
        from egregora.agents.profile.generator import generate_profile_posts

        ctx = Mock()
        ctx.config = Mock()
        ctx.config.models = Mock()
        ctx.config.models.writer = "gemini-2.0-flash"

        # 5 messages from one author
        messages = [
            {"author_uuid": "john-uuid", "author_name": "John", "text": f"Message {i}"} for i in range(5)
        ]

        # Track what was passed to content generator
        call_args = []

        async def capture_call(ctx, author_messages, **kwargs):
            call_args.append(len(author_messages))
            return "# Profile"

        with patch("egregora.agents.profile.generator._generate_profile_content", side_effect=capture_call):
            await generate_profile_posts(ctx, messages, "2025-03-07")

        # Should have received all 5 messages
        assert call_args[0] == 5

    @pytest.mark.asyncio
    async def test_llm_decides_content(self):
        """LLM analyzes history and decides what to write about."""
        from egregora.agents.profile.generator import ProfileUpdateDecision, _generate_profile_content

        ctx = Mock()
        ctx.config = Mock()
        ctx.config.models = Mock()
        ctx.config.models.writer = "gemini-2.0-flash"
        # Mock output format to avoid TypeError in _build_profile_prompt when accessing existing profile
        ctx.output_format = Mock()
        ctx.output_format.get_author_profile.return_value = None

        author_messages = [
            {"text": "I'm interested in AI safety", "timestamp": "2025-03-01"},
            {"text": "Mesa-optimization is concerning", "timestamp": "2025-03-02"},
            {"text": "We need better alignment", "timestamp": "2025-03-03"},
        ]

        # Mock LLM response
        with patch("egregora.agents.profile.generator._call_llm_decision") as mock_llm:
            mock_llm.return_value = ProfileUpdateDecision(
                significant=True,
                content="# John's AI Safety Focus\n\nJohn shows deep concern for AI alignment...",
            )

            content = await _generate_profile_content(
                ctx=ctx, author_messages=author_messages, author_name="John", author_uuid="john-uuid"
            )

        # Should have called LLM
        assert mock_llm.called

        # LLM should have received author's messages
        call_args = mock_llm.call_args[0]  # Positional args
        prompt = call_args[0]

        # Prompt should contain author's messages
        assert "AI safety" in prompt or "alignment" in prompt

        # Content should be what LLM returned
        assert "AI Safety Focus" in content


class TestProfilePrompt:
    """Test profile generation prompt structure."""

    def test_prompt_includes_full_history(self):
        """Prompt includes all messages from author."""
        from egregora.agents.profile.generator import _build_profile_prompt

        messages = [
            {"text": "Message 1", "timestamp": "2025-03-01"},
            {"text": "Message 2", "timestamp": "2025-03-02"},
            {"text": "Message 3", "timestamp": "2025-03-03"},
        ]

        prompt = _build_profile_prompt(author_name="John", author_messages=messages, window_date="2025-03-07")

        # All messages should be in prompt
        assert "Message 1" in prompt
        assert "Message 2" in prompt
        assert "Message 3" in prompt

    def test_prompt_asks_for_analysis(self):
        """Prompt asks LLM to analyze and decide content."""
        from egregora.agents.profile.generator import _build_profile_prompt

        prompt = _build_profile_prompt(
            author_name="Alice",
            author_messages=[{"text": "Test", "timestamp": "2025-03-01"}],
            window_date="2025-03-07",
        )

        # Should instruct LLM to analyze
        assert "analyze" in prompt.lower() or "analysis" in prompt.lower()

        # Should mention it's about the author
        assert "Alice" in prompt

        # Should ask for flattering/positive tone
        assert (
            "positive" in prompt.lower() or "flattering" in prompt.lower() or "appreciative" in prompt.lower()
        )

    def test_prompt_specifies_format(self):
        """Prompt specifies PROFILE post format."""
        from egregora.agents.profile.generator import _build_profile_prompt

        prompt = _build_profile_prompt(
            author_name="Bob",
            author_messages=[{"text": "Test", "timestamp": "2025-03-01"}],
            window_date="2025-03-07",
        )

        # Should specify it's a profile post
        assert "profile" in prompt.lower()

        # Should mention 1-2 paragraphs
        assert "paragraph" in prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
