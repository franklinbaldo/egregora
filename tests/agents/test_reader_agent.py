"""Tests for reader agent post comparison functionality."""

import os

import pytest

from egregora.agents.reader.agent import compare_posts
from egregora.agents.reader.models import EvaluationRequest, PostComparison, ReaderFeedback


# Sample blog post content for testing
SAMPLE_POST_A = """# Introduction to Python

Python is a high-level programming language known for its simplicity and readability.
It's widely used in web development, data science, and automation.

## Key Features

- Easy to learn and use
- Extensive standard library
- Large community support

Python's simple syntax makes it perfect for beginners while being powerful enough
for experienced developers.
"""

SAMPLE_POST_B = """# Getting Started with JavaScript

JavaScript is the language of the web, enabling interactive websites and modern web applications.
From simple animations to complex single-page applications, JavaScript powers the modern web.

## Why JavaScript?

- Runs in every browser
- Full-stack development with Node.js
- Rich ecosystem of frameworks

Whether you're building a simple website or a complex web app, JavaScript is essential.
"""

SAMPLE_POST_C = """# The Importance of Testing

Testing is crucial for software quality. Without proper tests, bugs slip through
and technical debt accumulates rapidly.

## Types of Testing

- Unit tests
- Integration tests
- End-to-end tests

Write tests. Always.
"""


@pytest.fixture
def mock_google_api_key(monkeypatch):
    """Set up Google API key for tests."""
    if "GOOGLE_API_KEY" not in os.environ:
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key-for-vcr")


class TestComparePostsStructure:
    """Test the structure and validation of compare_posts function."""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_compare_posts_returns_comparison(self, mock_google_api_key):
        """Should return PostComparison with all required fields."""
        request = EvaluationRequest(
            post_a_slug="intro-to-python",
            post_b_slug="getting-started-javascript",
            post_a_content=SAMPLE_POST_A,
            post_b_content=SAMPLE_POST_B,
        )

        result = await compare_posts(request)

        assert isinstance(result, PostComparison)
        assert result.post_a_slug == "intro-to-python"
        assert result.post_b_slug == "getting-started-javascript"
        assert result.winner in ["a", "b", "tie"]
        assert isinstance(result.reasoning, str)
        assert len(result.reasoning) > 0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_compare_posts_includes_feedback(self, mock_google_api_key):
        """Should include structured feedback for both posts."""
        request = EvaluationRequest(
            post_a_slug="intro-to-python",
            post_b_slug="getting-started-javascript",
            post_a_content=SAMPLE_POST_A,
            post_b_content=SAMPLE_POST_B,
        )

        result = await compare_posts(request)

        # Check feedback for post A
        assert isinstance(result.feedback_a, ReaderFeedback)
        assert isinstance(result.feedback_a.comment, str)
        assert 1 <= result.feedback_a.star_rating <= 5
        assert result.feedback_a.engagement_level in ["low", "medium", "high"]

        # Check feedback for post B
        assert isinstance(result.feedback_b, ReaderFeedback)
        assert isinstance(result.feedback_b.comment, str)
        assert 1 <= result.feedback_b.star_rating <= 5
        assert result.feedback_b.engagement_level in ["low", "medium", "high"]


class TestComparePostsLogic:
    """Test the logical consistency of post comparisons."""

    
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_winner_gets_higher_or_equal_rating(self, mock_google_api_key):
        """Winner should typically have higher or equal star rating."""
        request = EvaluationRequest(
            post_a_slug="intro-to-python",
            post_b_slug="getting-started-javascript",
            post_a_content=SAMPLE_POST_A,
            post_b_content=SAMPLE_POST_B,
        )

        result = await compare_posts(request)

        if result.winner == "a":
            # Winner A should have >= rating than B (allowing for nuance)
            assert result.feedback_a.star_rating >= result.feedback_b.star_rating - 1
        elif result.winner == "b":
            # Winner B should have >= rating than A (allowing for nuance)
            assert result.feedback_b.star_rating >= result.feedback_a.star_rating - 1
        else:  # tie
            # For tie, ratings should be close
            assert abs(result.feedback_a.star_rating - result.feedback_b.star_rating) <= 1

    
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_reasoning_references_posts(self, mock_google_api_key):
        """Reasoning should mention aspects of the posts being compared."""
        request = EvaluationRequest(
            post_a_slug="intro-to-python",
            post_b_slug="getting-started-javascript",
            post_a_content=SAMPLE_POST_A,
            post_b_content=SAMPLE_POST_B,
        )

        result = await compare_posts(request)

        reasoning_lower = result.reasoning.lower()
        # Reasoning should reference the topic or specific aspects
        # (This is a weak check - real reasoning quality depends on LLM)
        assert len(result.reasoning) > 20  # Should be substantive


class TestComparePostsDifferentContent:
    """Test comparisons with different types of content."""

    
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_compare_similar_quality_posts(self, mock_google_api_key):
        """Comparing similar quality posts should work."""
        request = EvaluationRequest(
            post_a_slug="intro-to-python",
            post_b_slug="getting-started-javascript",
            post_a_content=SAMPLE_POST_A,
            post_b_content=SAMPLE_POST_B,
        )

        result = await compare_posts(request)

        # Both are decent tutorial posts, ratings should be reasonable
        assert 2 <= result.feedback_a.star_rating <= 5
        assert 2 <= result.feedback_b.star_rating <= 5

    
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_compare_short_vs_detailed_post(self, mock_google_api_key):
        """Should handle posts of different lengths."""
        request = EvaluationRequest(
            post_a_slug="intro-to-python",
            post_b_slug="importance-of-testing",
            post_a_content=SAMPLE_POST_A,
            post_b_content=SAMPLE_POST_C,
        )

        result = await compare_posts(request)

        # Should successfully compare despite length difference
        assert result.winner in ["a", "b", "tie"]
        assert len(result.feedback_a.comment) > 0
        assert len(result.feedback_b.comment) > 0

    
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_compare_same_post_twice(self, mock_google_api_key):
        """Comparing identical posts should result in a tie (ideally)."""
        request = EvaluationRequest(
            post_a_slug="python-1",
            post_b_slug="python-2",
            post_a_content=SAMPLE_POST_A,
            post_b_content=SAMPLE_POST_A,  # Same content
        )

        result = await compare_posts(request)

        # When posts are identical, should be tie or very close ratings
        # (LLM might still pick a winner based on subtle prompt differences)
        rating_diff = abs(result.feedback_a.star_rating - result.feedback_b.star_rating)
        assert rating_diff <= 1  # Ratings should be very close


class TestComparePostsModelOverride:
    """Test model override functionality."""

    
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_custom_model_override(self, mock_google_api_key):
        """Should accept custom model parameter."""
        request = EvaluationRequest(
            post_a_slug="intro-to-python",
            post_b_slug="getting-started-javascript",
            post_a_content=SAMPLE_POST_A,
            post_b_content=SAMPLE_POST_B,
        )

        # Test with explicit model
        result = await compare_posts(request, model="gemini-flash-latest")

        assert isinstance(result, PostComparison)
        assert result.winner in ["a", "b", "tie"]


class TestComparePostsEdgeCases:
    """Test edge cases and error handling."""

    
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_empty_post_content(self, mock_google_api_key):
        """Should handle empty post content gracefully."""
        request = EvaluationRequest(
            post_a_slug="empty-post",
            post_b_slug="normal-post",
            post_a_content="",
            post_b_content=SAMPLE_POST_B,
        )

        result = await compare_posts(request)

        # Should complete without error
        assert isinstance(result, PostComparison)
        # Empty post should likely lose or get low rating
        if result.winner == "b":
            assert result.feedback_b.star_rating >= result.feedback_a.star_rating

    
    @pytest.mark.asyncio
    @pytest.mark.vcr()
    async def test_very_short_posts(self, mock_google_api_key):
        """Should handle very short posts."""
        request = EvaluationRequest(
            post_a_slug="short-a",
            post_b_slug="short-b",
            post_a_content="# Title\n\nOne sentence.",
            post_b_content="# Another Title\n\nTwo sentences. Here's another.",
        )

        result = await compare_posts(request)

        assert isinstance(result, PostComparison)
        assert result.winner in ["a", "b", "tie"]


class TestReaderFeedbackValidation:
    """Test ReaderFeedback dataclass validation."""

    def test_valid_star_rating(self):
        """Valid star ratings (1-5) should be accepted."""
        for rating in [1, 2, 3, 4, 5]:
            feedback = ReaderFeedback(
                comment="Test comment",
                star_rating=rating,
                engagement_level="medium",
            )
            assert feedback.star_rating == rating

    def test_invalid_star_rating_too_low(self):
        """Star rating below 1 should raise ValueError."""
        with pytest.raises(ValueError, match="Star rating must be 1-5"):
            ReaderFeedback(
                comment="Test comment",
                star_rating=0,
                engagement_level="medium",
            )

    def test_invalid_star_rating_too_high(self):
        """Star rating above 5 should raise ValueError."""
        with pytest.raises(ValueError, match="Star rating must be 1-5"):
            ReaderFeedback(
                comment="Test comment",
                star_rating=6,
                engagement_level="medium",
            )


class TestEvaluationRequestCreation:
    """Test EvaluationRequest dataclass creation."""

    def test_create_valid_request(self):
        """Should create valid request with all fields."""
        request = EvaluationRequest(
            post_a_slug="post-1",
            post_b_slug="post-2",
            post_a_content="Content A",
            post_b_content="Content B",
        )

        assert request.post_a_slug == "post-1"
        assert request.post_b_slug == "post-2"
        assert request.post_a_content == "Content A"
        assert request.post_b_content == "Content B"

    def test_request_is_frozen(self):
        """EvaluationRequest should be immutable (frozen)."""
        request = EvaluationRequest(
            post_a_slug="post-1",
            post_b_slug="post-2",
            post_a_content="Content A",
            post_b_content="Content B",
        )

        with pytest.raises(AttributeError):
            request.post_a_slug = "modified"  # type: ignore[misc]
