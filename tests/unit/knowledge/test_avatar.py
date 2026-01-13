"""Tests for avatar generation."""

from egregora.knowledge.avatar import generate_fallback_avatar_url


def test_generate_fallback_avatar_url_is_deterministic() -> None:
    """Verify that the avatar URL is deterministic for a given UUID."""
    author_uuid = "a-test-uuid"
    expected_url = (
        "https://avataaars.io/?accessoriesType=Kurt&avatarStyle=Circle&clotheType=ShirtVNeck"
        "&eyeType=Close&eyebrowType=DefaultNatural&facialHairType=Blank&hairColor=Black"
        "&mouthType=Concerned&skinColor=Pale&topType=WinterHat4"
    )

    actual_url = generate_fallback_avatar_url(author_uuid)

    assert actual_url == expected_url
