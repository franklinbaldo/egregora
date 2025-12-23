"""Tests for egregora.orchestration.pipelines.modules.media."""

from __future__ import annotations

from pathlib import Path

import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.orchestration.pipelines.modules.media import (
    MediaReplacer,
    detect_media_type,
    find_media_references,
    get_media_subfolder,
)


def test_media_replacer_image():
    """Test that MediaReplacer correctly replaces image references."""
    media_mapping = {
        "image.jpg": Document(
            content=b"",
            type=DocumentType.MEDIA,
            metadata={
                "media_type": "image",
                "public_url": "/media/images/image.jpg",
                "filename": "image.jpg",
            },
        )
    }
    replacer = MediaReplacer(media_mapping)
    text = "Here is an image: image.jpg (file attached)"
    expected = "Here is an image: ![Image](/media/images/image.jpg)"
    assert replacer.replace(text) == expected


def test_media_replacer_other_media():
    """Test that MediaReplacer correctly replaces non-image media references."""
    media_mapping = {
        "document.pdf": Document(
            content=b"",
            type=DocumentType.MEDIA,
            metadata={
                "media_type": "document",
                "public_url": "/media/documents/document.pdf",
                "filename": "document.pdf",
            },
        )
    }
    replacer = MediaReplacer(media_mapping)
    text = "Here is a document: document.pdf"
    expected = "Here is a document: [document.pdf](/media/documents/document.pdf)"
    assert replacer.replace(text) == expected


def test_media_replacer_no_match():
    """Test that MediaReplacer does not replace text that is not a media reference."""
    media_mapping = {
        "image.jpg": Document(
            content=b"",
            type=DocumentType.MEDIA,
            metadata={"media_type": "image", "public_url": "/media/images/image.jpg"},
        )
    }
    replacer = MediaReplacer(media_mapping)
    text = "This is a regular text without any media."
    assert replacer.replace(text) == text


def test_media_replacer_case_insensitive():
    """Test that MediaReplacer performs case-insensitive matching."""
    media_mapping = {
        "IMAGE.JPG": Document(
            content=b"",
            type=DocumentType.MEDIA,
            metadata={"media_type": "image", "public_url": "/media/images/IMAGE.JPG"},
        )
    }
    replacer = MediaReplacer(media_mapping)
    text = "Here is an image: image.jpg"
    expected = "Here is an image: ![Image](/media/images/IMAGE.JPG)"
    assert replacer.replace(text) == expected


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        ("image.jpg", "image"),
        ("photo.png", "image"),
        ("video.mp4", "video"),
        ("clip.mov", "video"),
        ("song.mp3", "audio"),
        ("podcast.opus", "audio"),
        ("document.pdf", "document"),
        ("report.docx", "document"),
        ("archive.zip", None),
        ("file", None),
    ],
)
def test_detect_media_type(filename, expected_type):
    """Test that detect_media_type correctly identifies media types from file extensions."""
    assert detect_media_type(Path(filename)) == expected_type


@pytest.mark.parametrize(
    ("extension", "expected_folder"),
    [
        (".jpg", "images"),
        (".png", "images"),
        (".mp4", "videos"),
        (".mov", "videos"),
        (".mp3", "audio"),
        (".opus", "audio"),
        (".pdf", "documents"),
        (".docx", "documents"),
        (".zip", "files"),
        ("", "files"),
    ],
)
def test_get_media_subfolder(extension, expected_folder):
    """Test that get_media_subfolder returns the correct subfolder for a given file extension."""
    assert get_media_subfolder(extension) == expected_folder


@pytest.mark.parametrize(
    ("text", "expected_references"),
    [
        ("Here is a file: IMG-20230101-WA0001.jpg (file attached)", ["IMG-20230101-WA0001.jpg"]),
        ("Check out this video: VID-20230101-WA0002.mp4", ["VID-20230101-WA0002.mp4"]),
        ("\u200eAUD-20230101-WA0003.opus", ["AUD-20230101-WA0003.opus"]),
        (
            "IMG-20230101-WA0001.jpg (file attached) and VID-20230101-WA0002.mp4",
            ["IMG-20230101-WA0001.jpg", "VID-20230101-WA0002.mp4"],
        ),
        ("No media here.", []),
        (
            "IMG-20230101-WA0001.jpg and IMG-20230101-WA0001.jpg",
            ["IMG-20230101-WA0001.jpg"],
        ),
    ],
)
def test_find_media_references(text, expected_references):
    """Test that find_media_references correctly extracts media references from text."""
    assert sorted(find_media_references(text)) == sorted(expected_references)
