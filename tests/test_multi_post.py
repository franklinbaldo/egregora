"""Tests for multi-post generation with function calling."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from egregora.config import PipelineConfig
from egregora.generator import PostContext, PostGenerator
from egregora.tools import sanitize_slug


@pytest.fixture
def mock_gemini_manager(monkeypatch):
    """Mock GeminiManager to avoid actual API calls."""
    mock_manager = MagicMock()
    monkeypatch.setattr("egregora.generator.GeminiManager", lambda **kwargs: mock_manager)
    return mock_manager


@pytest.fixture
def mock_prompt_loader(monkeypatch):
    """Mock PromptLoader to provide test prompts."""
    def mock_load_text(self, filename):
        return f"# Test prompt: {filename}"

    monkeypatch.setattr("egregora.generator.PromptLoader.load_text", mock_load_text)


def test_generate_posts_with_tools_mode(mock_gemini_manager, mock_prompt_loader):
    """Test that generate_posts can work with function calling."""
    config = PipelineConfig()
    generator = PostGenerator(config)

    # Mock response with function calls
    mock_response = Mock()
    mock_response.candidates = []

    # Create mock candidate with function calls
    mock_candidate = Mock()
    mock_part1 = Mock()
    # Configure function_call with proper attributes
    fc1 = Mock()
    fc1.name = "write_post"
    fc1.args = {
        "title": "First Thread",
        "slug": "first-thread",
        "content": "---\ndate: 2025-01-01\n---\n\nContent of first thread",
        "participants": ["uuid1", "uuid2"],
    }
    mock_part1.function_call = fc1

    mock_part2 = Mock()
    # Configure function_call with proper attributes
    fc2 = Mock()
    fc2.name = "write_post"
    fc2.args = {
        "title": "Second Thread",
        "slug": "second-thread",
        "content": "---\ndate: 2025-01-01\n---\n\nContent of second thread",
        "participants": ["uuid3", "uuid4"],
    }
    mock_part2.function_call = fc2

    mock_candidate.content = Mock()
    mock_candidate.content.parts = [mock_part1, mock_part2]
    mock_response.candidates = [mock_candidate]

    # Configure mock to return our response (as async)
    async def mock_generate(*args, **kwargs):
        return mock_response

    mock_gemini_manager.generate_content = mock_generate

    # Create test context
    source = Mock()
    source.is_virtual = False
    source.name = "Test Group"

    context = PostContext(
        group_name="Test Group",
        transcript="Test transcript",
        target_date=date(2025, 1, 1),
    )

    # Execute
    posts = generator.generate_posts(source, context, use_tools=True)

    # Assert
    assert len(posts) == 2
    assert posts[0]["title"] == "First Thread"
    assert posts[0]["slug"] == "first-thread"
    assert "Content of first thread" in posts[0]["content"]
    assert posts[0]["participants"] == ["uuid1", "uuid2"]

    assert posts[1]["title"] == "Second Thread"
    assert posts[1]["slug"] == "second-thread"
    assert "Content of second thread" in posts[1]["content"]
    assert posts[1]["participants"] == ["uuid3", "uuid4"]


def test_generate_posts_fallback_without_function_calls(mock_gemini_manager, mock_prompt_loader):
    """Test fallback to text response when LLM doesn't use function calling."""
    config = PipelineConfig()
    generator = PostGenerator(config)

    # Mock response without function calls (just text)
    mock_response = Mock()
    mock_response.text = "---\ndate: 2025-01-01\n---\n\nSingle post content"
    mock_candidate = Mock()
    mock_candidate.content = Mock()
    mock_candidate.content.parts = []
    mock_response.candidates = [mock_candidate]

    async def mock_generate(*args, **kwargs):
        return mock_response

    mock_gemini_manager.generate_content = mock_generate

    source = Mock()
    source.is_virtual = False
    source.name = "Test Group"

    context = PostContext(
        group_name="Test Group",
        transcript="Test transcript",
        target_date=date(2025, 1, 1),
    )

    # Execute
    posts = generator.generate_posts(source, context, use_tools=True)

    # Assert fallback behavior
    assert len(posts) == 1
    assert posts[0]["title"] == "Daily Post"
    assert posts[0]["slug"] == "daily-post"
    assert "Single post content" in posts[0]["content"]


def test_generate_legacy_mode_returns_string(mock_gemini_manager, mock_prompt_loader):
    """Test that legacy generate() method still returns a string."""
    config = PipelineConfig()
    generator = PostGenerator(config)

    # Mock response
    mock_response = Mock()
    mock_response.text = "Legacy post content"
    mock_candidate = Mock()
    mock_candidate.content = Mock()
    mock_candidate.content.parts = []
    mock_response.candidates = [mock_candidate]

    async def mock_generate(*args, **kwargs):
        return mock_response

    mock_gemini_manager.generate_content = mock_generate

    source = Mock()
    source.is_virtual = False
    source.name = "Test Group"

    context = PostContext(
        group_name="Test Group",
        transcript="Test transcript",
        target_date=date(2025, 1, 1),
    )

    # Execute legacy method
    post_text = generator.generate(source, context)

    # Assert returns string
    assert isinstance(post_text, str)
    assert "Legacy post content" in post_text


def test_sanitize_slug():
    """Test slug sanitization function."""
    # Basic sanitization
    assert sanitize_slug("A Pacificação Social") == "a-pacificacao-social"
    assert sanitize_slug("Frameworks vs Simplicidade") == "frameworks-vs-simplicidade"

    # Remove special characters
    assert sanitize_slug("Frameworks vs Simplicidade!!!") == "frameworks-vs-simplicidade"
    assert sanitize_slug("Test@#$%Post") == "testpost"

    # Replace spaces and underscores with hyphens
    assert sanitize_slug("Artigo_sobre_IA") == "artigo-sobre-ia"
    assert sanitize_slug("Test   Multiple   Spaces") == "test-multiple-spaces"

    # Remove accents
    assert sanitize_slug("São Paulo Ação") == "sao-paulo-acao"
    assert sanitize_slug("Café com Açúcar") == "cafe-com-acucar"

    # Lowercase
    assert sanitize_slug("UPPERCASE TEXT") == "uppercase-text"

    # Truncate long slugs
    long_slug = "a" * 100
    result = sanitize_slug(long_slug)
    assert len(result) <= 50

    # Empty string fallback
    assert sanitize_slug("") == "post"
    assert sanitize_slug("@#$%") == "post"

    # Multiple consecutive hyphens
    assert sanitize_slug("test---multiple---hyphens") == "test-multiple-hyphens"

    # Leading/trailing hyphens
    assert sanitize_slug("-test-slug-") == "test-slug"
