from __future__ import annotations

import sys
import uuid
from datetime import date
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.media_extractor import MediaExtractor, MediaFile


def test_extract_media_from_zip_creates_files(tmp_path) -> None:
    zip_path = Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")
    group_dir = tmp_path / "posts" / "grupo-teste"
    extractor = MediaExtractor(group_dir, group_slug="grupo-teste")

    media_files = extractor.extract_media_from_zip(
        zip_path, date(2025, 10, 3)
    )

    assert "IMG-20251002-WA0004.jpg" in media_files
    media = media_files["IMG-20251002-WA0004.jpg"]
    assert media.dest_path.exists()
    expected_path = PurePosixPath("grupo-teste", "media", media.dest_path.name)
    assert media.relative_path == expected_path.as_posix()


def test_replace_media_references_converts_to_markdown() -> None:
    media = MediaFile(
        filename="IMG-20251002-WA0004.jpg",
        media_type="image",
        source_path="IMG-20251002-WA0004.jpg",
        dest_path=Path(
            "data/posts/grupo-teste/media/IMG-20251002-WA0004.jpg"
        ),
        relative_path="grupo-teste/media/IMG-20251002-WA0004.jpg",
    )
    text = (
        "03/10/2025 09:46 - Franklin: \u200eIMG-20251002-WA0004.jpg (arquivo anexado)"
    )

    updated = MediaExtractor.replace_media_references(
        text,
        {"IMG-20251002-WA0004.jpg": media},
    )

    assert (
        "![IMG-20251002-WA0004.jpg](grupo-teste/media/IMG-20251002-WA0004.jpg)"
        in updated
    )
    assert "_(arquivo anexado)_" in updated


def test_build_public_paths_relative(tmp_path) -> None:
    zip_path = Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")
    extractor = MediaExtractor(tmp_path / "posts" / "grupo", group_slug="grupo")

    media_files = extractor.extract_media_from_zip(
        zip_path, date(2025, 10, 3)
    )

    output_dir = tmp_path / "docs" / "posts"
    output_dir.mkdir(parents=True)

    public_paths = MediaExtractor.build_public_paths(media_files, relative_to=output_dir)
    media = media_files["IMG-20251002-WA0004.jpg"]
    path = public_paths["IMG-20251002-WA0004.jpg"]

    assert path.startswith("../../posts/grupo/media/")
    assert path.endswith(media.filename)


def test_build_public_paths_with_prefix(tmp_path) -> None:
    zip_path = Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")
    extractor = MediaExtractor(tmp_path / "posts" / "grupo", group_slug="grupo")

    media_files = extractor.extract_media_from_zip(
        zip_path, date(2025, 10, 3)
    )

    public_paths = MediaExtractor.build_public_paths(media_files, url_prefix="/media")
    # The key is the original name, but the value inside media_files is the new name
    media = media_files["IMG-20251002-WA0004.jpg"]
    path = public_paths["IMG-20251002-WA0004.jpg"]

    assert path.startswith("/media/grupo/")
    # The path should now end with the new UUID-based filename
    assert path.endswith(media.filename)


def test_extract_media_renames_to_uuid_and_updates_reference(tmp_path) -> None:
    """
    Tests that media files are renamed to a stable UUID and that references
    in the text are updated to use the new UUID filename.
    """
    zip_path = Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")
    extractor = MediaExtractor(
        tmp_path / "posts" / "grupo-uuid-teste", group_slug="grupo-uuid-teste"
    )
    original_filename = "IMG-20251002-WA0004.jpg"

    # 1. Extract media
    media_files = extractor.extract_media_from_zip(
        zip_path, date(2025, 10, 3)
    )

    # 2. Verify the file was renamed to UUID format
    assert original_filename in media_files
    media = media_files[original_filename]

    # Check if the new filename is a valid UUID
    new_stem = Path(media.filename).stem
    try:
        uuid.UUID(new_stem)
    except ValueError:
        assert False, f"Filename stem '{new_stem}' is not a valid UUID."

    assert media.filename.endswith(".jpg")
    assert media.dest_path.exists()
    assert media.dest_path.name == media.filename

    # 3. Verify the text reference is updated correctly
    text = f"03/10/2025 09:46 - Franklin: \u200e{original_filename} (arquivo anexado)"
    updated_text = MediaExtractor.replace_media_references(
        text,
        media_files,
    )

    # The markdown reference should use the new UUID-based filename
    expected_markdown_link = f"![{media.filename}]({media.relative_path})"

    assert original_filename not in updated_text
    assert media.filename in updated_text
    assert expected_markdown_link in updated_text
    assert "_(arquivo anexado)_" in updated_text
