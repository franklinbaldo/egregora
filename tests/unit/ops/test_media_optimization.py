import pytest

from egregora.ops.media import find_all_media_references


@pytest.mark.parametrize(
    "message, row, expected_refs",
    [
        # Plain text file
        ("Check out file.jpg", {}, {"file.jpg"}),
        # Markdown link
        ("Here is [a link](http://example.com/doc.pdf)", {}, {"doc.pdf"}),
        ("Here is ![image](img.png)", {}, {"img.png"}),
        # WA file
        ("IMG-20230101-WA0001.jpg", {}, {"IMG-20230101-WA0001.jpg"}),
        # UUID file
        # If media_type=True, include all UUIDs (even without extension if regex matched it, but regex requires extension usually)
        # Our regex requires \.\w+ for UUIDs.
        (
            "12345678-1234-1234-1234-1234567890ab.png",
            {"media_type": True},
            {"12345678-1234-1234-1234-1234567890ab.png"},
        ),
        # If media_type=False, include UUID only if it has known extension
        (
            "12345678-1234-1234-1234-1234567890ab.png",
            {"media_type": False},
            {"12345678-1234-1234-1234-1234567890ab.png"},
        ),
        # UUID with unknown extension
        (
            "12345678-1234-1234-1234-1234567890ab.xyz",
            {"media_type": True},
            {"12345678-1234-1234-1234-1234567890ab.xyz"},
        ),
        ("12345678-1234-1234-1234-1234567890ab.xyz", {"media_type": False}, set()),
        # Marker
        ("report.pdf (file attached)", {}, {"report.pdf"}),
        # Mixed
        ("See img.jpg and [doc](doc.pdf)", {}, {"img.jpg", "doc.pdf"}),
        # Overlapping (md link contains filename that matches file pattern)
        ("[text](foo.jpg)", {}, {"foo.jpg"}),
        # No match
        ("Just text", {}, set()),
    ],
)
def test_find_all_media_references(message, row, expected_refs):
    """Verify find_all_media_references behavior."""
    refs = set(find_all_media_references(message, include_uuids=bool(row.get("media_type"))))
    assert refs == expected_refs


def test_legacy_overlap_behavior_preserved():
    """Documenting behavior of overlapping patterns (preserved from legacy)."""
    message = "![img](http://site.com/pic.jpg)"
    # Markdown link pattern finds "pic.jpg"
    # Generic pattern finds "pic.jpg"
    # Result: "pic.jpg" (deduplicated)
    refs = set(find_all_media_references(message))
    assert "pic.jpg" in refs
    assert len(refs) == 1
