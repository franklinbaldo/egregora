from datetime import UTC, datetime
from pathlib import Path

import pytest
from egregora_v3.infra.adapters.rss import RSSAdapter


@pytest.fixture
def rss_file(tmp_path):
    """Creates a dummy RSS file."""
    content = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>http://example.org/</link>
    <description>A test feed</description>
    <item>
      <title>Test Item</title>
      <link>http://example.org/item1</link>
      <guid>http://example.org/item1</guid>
      <pubDate>Wed, 04 Dec 2024 12:00:00 GMT</pubDate>
      <description>This is a summary.</description>
      <author>alice@example.org (Alice)</author>
    </item>
  </channel>
</rss>
"""
    file_path = tmp_path / "feed.xml"
    file_path.write_text(content)
    return file_path


def test_rss_adapter_parses_rss2(rss_file):
    adapter = RSSAdapter()
    entries = list(adapter.parse(rss_file))

    assert len(entries) == 1
    entry = entries[0]

    assert entry.id == "http://example.org/item1"
    assert entry.title == "Test Item"
    assert entry.summary == "This is a summary."
    # Author parsing in RSS 2.0 can be tricky with feedparser, usually puts it in 'author'
    # feedparser often normalizes "email (Name)" to author_detail
    # Let's check what we got
    assert len(entry.authors) > 0
    # Allow loose matching since feedparser is smart
    assert "Alice" in entry.authors[0].name or "alice@example.org" in entry.authors[0].name

    # Date check
    assert entry.updated.year == 2024
    assert entry.updated.month == 12
    assert entry.updated.day == 4


def test_rss_adapter_malformed_file(tmp_path):
    bad_file = tmp_path / "bad.xml"
    bad_file.write_text("This is not XML")

    adapter = RSSAdapter()
    with pytest.raises(ValueError):
        list(adapter.parse(bad_file))


def test_rss_adapter_file_not_found():
    adapter = RSSAdapter()
    with pytest.raises(FileNotFoundError):
        list(adapter.parse(Path("nonexistent.xml")))


def test_rss_adapter_parses_url_string(mocker):
    """Test parsing a URL string (mocked feedparser)."""
    # Mock feedparser.parse to simulate URL fetch
    mock_entry = {
        "id": "http://example.org/remote",
        "title": "Remote Item",
        "link": "http://example.org/remote",
        "updated_parsed": None,
        "published_parsed": None,
    }
    mock_feed = mocker.Mock()
    mock_feed.bozo = 0
    mock_feed.entries = [mock_entry]

    mocker.patch("feedparser.parse", return_value=mock_feed)

    adapter = RSSAdapter()
    entries = list(adapter.parse("http://example.org/feed.rss"))

    assert len(entries) == 1
    assert entries[0].id == "http://example.org/remote"

    # Verify feedparser was called with the URL
    import feedparser
    feedparser.parse.assert_called_with("http://example.org/feed.rss")


def test_entry_serialization_works(rss_file):
    """Test that Entry produced by RSSAdapter is JSON serializable."""
    adapter = RSSAdapter()
    entries = list(adapter.parse(rss_file))

    assert len(entries) > 0
    entry = entries[0]

    # Should not raise TypeError: Object of type struct_time is not JSON serializable
    json_str = entry.model_dump_json()
    assert len(json_str) > 0
    assert "feedparser_original" in json_str
    # Verify _parsed fields are gone
    assert "published_parsed" not in json_str
