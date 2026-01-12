"""Unit tests for the avatar generation module."""

import uuid

from egregora.knowledge import avatar


def test_generate_fallback_avatar_url_returns_valid_url():
    """Should return a valid URL from avataaars.io."""
    author_uuid = str(uuid.uuid4())
    url = avatar.generate_fallback_avatar_url(author_uuid)
    assert url.startswith("https://avataaars.io/")
    assert "avatarStyle=Circle" in url
    assert "topType=" in url
    assert "accessoriesType=" in url
    assert "hairColor=" in url
    assert "facialHairType=" in url
    assert "clotheType=" in url
    assert "eyeType=" in url
    assert "eyebrowType=" in url
    assert "mouthType=" in url
    assert "skinColor=" in url
