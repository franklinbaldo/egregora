from __future__ import annotations

import sys
import uuid
from datetime import date, datetime
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import polars as pl
import pytest

from egregora.media_extractor import MediaExtractor, MediaFile


def test_extract_media_from_zip_creates_files(tmp_path) -> None:
    zip_path = Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")
    group_dir = tmp_path / "posts" / "grupo-teste"
    extractor = MediaExtractor(group_dir, group_slug="grupo-teste")

    media_files = extractor.extract_media_from_zip(zip_path, date(2025, 10, 3))

    assert "IMG-20251002-WA0004.jpg" in media_files
    media = media_files["IMG-20251002-WA0004.jpg"]
    assert media.dest_path.exists()
    expected_path = PurePosixPath("grupo-teste", "media", "images", media.dest_path.name)
    assert media.relative_path == expected_path.as_posix()


def test_build_public_paths_relative(tmp_path) -> None:
    zip_path = Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")
    extractor = MediaExtractor(tmp_path / "posts" / "grupo", group_slug="grupo")

    media_files = extractor.extract_media_from_zip(zip_path, date(2025, 10, 3))

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

    media_files = extractor.extract_media_from_zip(zip_path, date(2025, 10, 3))

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
    media_files = extractor.extract_media_from_zip(zip_path, date(2025, 10, 3))

    # 2. Verify the file was renamed to UUID format
    assert original_filename in media_files
    media = media_files[original_filename]

    # Check if the new filename is a valid UUID
    new_stem = Path(media.filename).stem
    try:
        uuid.UUID(new_stem)
    except ValueError:
        pytest.fail(f"Filename stem '{new_stem}' is not a valid UUID.")

    assert media.filename.endswith(".jpg")
    assert media.dest_path.exists()
    assert media.dest_path.name == media.filename

    # 3. Verify the text reference is updated correctly
    df = pl.DataFrame(
        {
            "date": [date(2025, 10, 3)],
            "timestamp": [datetime(2025, 10, 3, 9, 46)],
            "author": ["Franklin"],
            "message": [
                f"03/10/2025 09:46 - Franklin: \u200e{original_filename} (arquivo anexado)"
            ],
        }
    )

    updated_df = MediaExtractor.replace_media_references_dataframe(
        df,
        media_files,
    )

    rendered = updated_df.get_column("message")[0]
    expected_markdown_link = f"![{media.filename}]({media.relative_path})"

    assert original_filename not in rendered
    assert media.filename in rendered
    assert expected_markdown_link in rendered
    assert "_(arquivo anexado)_" in rendered


def test_replace_media_references_dataframe_handles_multiple_attachments(tmp_path) -> None:
    dest_image = tmp_path / "media" / "images" / "img-1.jpg"
    dest_image.parent.mkdir(parents=True, exist_ok=True)
    dest_image.touch()

    dest_doc = tmp_path / "media" / "documents" / "doc-1.pdf"
    dest_doc.parent.mkdir(parents=True, exist_ok=True)
    dest_doc.touch()

    media_files = {
        "IMG-20250101-WA0001.jpg": MediaFile(
            filename="11111111-1111-1111-1111-111111111111.jpg",
            media_type="image",
            source_path="IMG-20250101-WA0001.jpg",
            dest_path=dest_image,
            relative_path="grupo/media/images/11111111-1111-1111-1111-111111111111.jpg",
        ),
        "Relatorio Final.pdf": MediaFile(
            filename="22222222-2222-2222-2222-222222222222.pdf",
            media_type="document",
            source_path="Relatorio Final.pdf",
            dest_path=dest_doc,
            relative_path="grupo/media/documents/22222222-2222-2222-2222-222222222222.pdf",
        ),
    }

    df = pl.DataFrame(
        {
            "message": [
                (
                    "01/01/2025 08:30 - Alice: \u200eIMG-20250101-WA0001.jpg (arquivo anexado)\n"
                    "Relatorio Final.pdf (Archivo Adjunto)"
                )
            ]
        }
    )

    updated_df = MediaExtractor.replace_media_references_dataframe(df, media_files)
    rendered = updated_df.get_column("message")[0]

    expected_image = (
        "![11111111-1111-1111-1111-111111111111.jpg]"
        "(grupo/media/images/11111111-1111-1111-1111-111111111111.jpg)"
    )
    expected_document = (
        "[📄 22222222-2222-2222-2222-222222222222.pdf]"
        "(grupo/media/documents/22222222-2222-2222-2222-222222222222.pdf)"
    )

    assert "IMG-20250101-WA0001.jpg" not in rendered
    assert "Relatorio Final.pdf (Archivo Adjunto)" not in rendered
    assert expected_image in rendered
    assert expected_document in rendered
    assert "_(arquivo anexado)_" in rendered
    assert "_(Archivo Adjunto)_" in rendered


def test_replace_media_references_dataframe_preserves_unknown_attachments(tmp_path) -> None:
    dest_audio = tmp_path / "media" / "audio" / "aud-1.opus"
    dest_audio.parent.mkdir(parents=True, exist_ok=True)
    dest_audio.touch()

    known_media = MediaFile(
        filename="33333333-3333-3333-3333-333333333333.opus",
        media_type="audio",
        source_path="Audio.opus",
        dest_path=dest_audio,
        relative_path="grupo/media/audio/33333333-3333-3333-3333-333333333333.opus",
    )

    media_files = {"Audio.opus": known_media}

    df = pl.DataFrame(
        {
            "message": [
                (
                    "02/02/2025 10:00 - Bruno: Audio.opus (Arquivo Anexado)\n"
                    "Documento Secreto.pdf (arquivo anexado)"
                )
            ]
        }
    )

    updated_df = MediaExtractor.replace_media_references_dataframe(df, media_files)
    rendered = updated_df.get_column("message")[0]

    expected_audio = (
        "[🔊 33333333-3333-3333-3333-333333333333.opus]"
        "(grupo/media/audio/33333333-3333-3333-3333-333333333333.opus)"
    )

    assert expected_audio in rendered
    assert "Audio.opus (Arquivo Anexado)" not in rendered
    assert "Documento Secreto.pdf (arquivo anexado)" in rendered


def test_find_attachment_names_dataframe_handles_multiline_and_languages() -> None:
    df = pl.DataFrame(
        {
            "timestamp": [datetime(2024, 12, 12, 12, 0)],
            "author": ["Alice"],
            "message": [
                (
                    "12/12/2024, 12:00 - Alice: \u200eIMG-20241212-WA0001.jpg (arquivo anexado)\n"
                    "Vídeo Final.MP4 (File Attached)\n"
                    "Notas Apresentação.pptx (archivo adjunto)"
                )
            ],
        }
    )

    attachments = MediaExtractor.find_attachment_names_dataframe(df)

    assert attachments == {
        "IMG-20241212-WA0001.jpg",
        "Vídeo Final.MP4",
        "Notas Apresentação.pptx",
    }


def test_find_attachment_names_dataframe_uses_tagged_and_original_lines() -> None:
    df = pl.DataFrame(
        {
            "timestamp": [datetime(2024, 7, 10, 9, 15), datetime(2024, 7, 10, 9, 16)],
            "author": ["Bob", "Carlos"],
            "message": [None, "Sem anexo"],
            "tagged_line": [
                (
                    "Bob: Documento Assinado.sig (arquivo anexado)\n"
                    "Bob: Reunião.opus (File Attached)"
                ),
                None,
            ],
            "original_line": [
                None,
                (
                    "Carlos: Relatório Final.pdf (Archivo Adjunto)\n"
                    "Linha sem anexo"
                ),
            ],
        }
    )

    attachments = MediaExtractor.find_attachment_names_dataframe(df)

    assert attachments == {
        "Documento Assinado.sig",
        "Reunião.opus",
        "Relatório Final.pdf",
    }
