"""Essentialist tests for core types."""
import pytest

from egregora_v3.core.types import Entry, Link


@pytest.mark.parametrize(
    "links, expected",
    [
        ([], False),
        ([Link(href="http://example.com", rel="alternate")], False),
        ([Link(href="http://example.com/img.png", rel="enclosure", type="image/png")], True),
        ([Link(href="http://example.com/audio.mp3", rel="enclosure", type="audio/mpeg")], True),
        ([Link(href="http://example.com/video.mp4", rel="enclosure", type="video/mp4")], True),
        (
            [
                Link(href="http://example.com", rel="alternate"),
                Link(href="http://example.com/img.png", rel="enclosure", type="image/png"),
            ],
            True,
        ),
    ],
)
def test_entry_has_enclosure_property(links: list[Link], expected: bool):
    """Test the `has_enclosure` property on the `Entry` model."""
    entry = Entry(
        id="test",
        title="test",
        updated="2024-01-01T00:00:00Z",
        links=links,
    )
    assert entry.has_enclosure == expected
