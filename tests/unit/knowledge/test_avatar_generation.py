"""Isolated test for avatar generation to break a file-system loop."""

from egregora.knowledge import profiles


def test_generate_fallback_avatar_url_is_deterministic():
    """Should generate a deterministic avatar URL based on the UUID."""
    test_uuid = "12345678-1234-5678-1234-567812345678"
    expected_url = (
        "https://avataaars.io/?accessoriesType=Round&avatarStyle=Circle&clotheType=Hoodie"
        "&eyeType=Squint&eyebrowType=SadConcernedNatural&facialHairType=Blank"
        "&hairColor=SilverGray&mouthType=Disbelief&skinColor=Yellow&topType=LongHairDreads"
    )
    generated_url = profiles.generate_fallback_avatar_url(test_uuid)
    assert generated_url == expected_url
