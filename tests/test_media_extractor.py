from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.media_extractor import MediaExtractor, MediaFile


def test_extract_media_from_zip_creates_files(tmp_path) -> None:
    zip_path = Path("tests/data/Conversa do WhatsApp com Teste.zip")
    extractor = MediaExtractor(tmp_path / "media")

    media_files = extractor.extract_media_from_zip(zip_path, date(2025, 10, 3))

    assert "IMG-20251002-WA0004.jpg" in media_files
    media = media_files["IMG-20251002-WA0004.jpg"]
    assert media.dest_path.exists()
    assert media.relative_path == "media/2025-10-03/IMG-20251002-WA0004.jpg"


def test_replace_media_references_converts_to_markdown() -> None:
    media = MediaFile(
        filename="IMG-20251002-WA0004.jpg",
        media_type="image",
        source_path="IMG-20251002-WA0004.jpg",
        dest_path=Path("media/2025-10-03/IMG-20251002-WA0004.jpg"),
        relative_path="media/2025-10-03/IMG-20251002-WA0004.jpg",
    )
    text = (
        "03/10/2025 09:46 - Franklin: \u200eIMG-20251002-WA0004.jpg (arquivo anexado)"
    )

    updated = MediaExtractor.replace_media_references(
        text,
        {"IMG-20251002-WA0004.jpg": media},
    )

    assert "![IMG-20251002-WA0004.jpg](media/2025-10-03/IMG-20251002-WA0004.jpg)" in updated
    assert "_(arquivo anexado)_" in updated


def test_build_public_paths_relative(tmp_path) -> None:
    zip_path = Path("tests/data/Conversa do WhatsApp com Teste.zip")
    extractor = MediaExtractor(tmp_path / "media")

    media_files = extractor.extract_media_from_zip(zip_path, date(2025, 10, 3))

    output_dir = tmp_path / "docs" / "reports"
    output_dir.mkdir(parents=True)

    public_paths = MediaExtractor.build_public_paths(media_files, relative_to=output_dir)
    path = public_paths["IMG-20251002-WA0004.jpg"]

    assert path.startswith("../../media/2025-10-03/")
    assert path.endswith("IMG-20251002-WA0004.jpg")


def test_build_public_paths_with_prefix(tmp_path) -> None:
    zip_path = Path("tests/data/Conversa do WhatsApp com Teste.zip")
    extractor = MediaExtractor(tmp_path / "media")

    media_files = extractor.extract_media_from_zip(zip_path, date(2025, 10, 3))

    public_paths = MediaExtractor.build_public_paths(media_files, url_prefix="/media")
    path = public_paths["IMG-20251002-WA0004.jpg"]

    assert path.startswith("/media/2025-10-03/")
    assert path.endswith("IMG-20251002-WA0004.jpg")
