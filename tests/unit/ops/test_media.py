from pathlib import Path

from egregora.ops.media import (
    ATTACHMENT_MARKERS,
    detect_media_type,
    find_media_references,
    get_media_subfolder,
)


def test_detect_media_type():
    """Should correctly identify media types from extensions."""
    assert detect_media_type(Path("image.jpg")) == "image"
    assert detect_media_type(Path("video.mp4")) == "video"
    assert detect_media_type(Path("audio.mp3")) == "audio"
    assert detect_media_type(Path("doc.pdf")) == "document"
    assert detect_media_type(Path("unknown.xyz")) is None


def test_get_media_subfolder():
    """Should return correct subfolder for media types."""
    assert get_media_subfolder(".jpg") == "images"
    assert get_media_subfolder(".mp4") == "videos"
    assert get_media_subfolder(".pdf") == "documents"
    assert get_media_subfolder(".xyz") == "files"


def test_find_media_references_whatsapp():
    """Should extract standard WhatsApp media references."""
    text = "Here is a photo IMG-20230101-WA0001.jpg (file attached)"
    refs = find_media_references(text)
    assert refs == ["IMG-20230101-WA0001.jpg"]


def test_find_media_references_unicode():
    """Should extract WhatsApp media references with unicode markers."""
    # U+200E is implicit in some regexes, but let's test the explicit case if possible
    text = "\u200eIMG-20230101-WA0002.jpg"
    refs = find_media_references(text)
    assert refs == ["IMG-20230101-WA0002.jpg"]


def test_find_media_references_various_markers():
    """Should extract media references using various localized markers."""
    for marker in ATTACHMENT_MARKERS:
        filename = "test_image.png"
        text = f"{filename} {marker}"
        refs = find_media_references(text)
        assert refs == [filename], f"Failed to match marker: {marker}"
