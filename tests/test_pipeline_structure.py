from textwrap import dedent

import pytest

from egregora.pipeline import _migrate_legacy_structure, process_whatsapp_export
from egregora.site_config import resolve_site_paths


def test_process_requires_mkdocs(tmp_path):
    """Processing without a MkDocs scaffold should fail fast."""
    output_dir = tmp_path / "site"

    with pytest.raises(ValueError, match="mkdocs\\.yml"):
        process_whatsapp_export(
            zip_path=tmp_path / "dummy.zip",
            output_dir=output_dir,
            enable_enrichment=False,
        )


def test_process_requires_docs_structure(tmp_path):
    """Processing should fail if docs_dir declared in mkdocs.yml does not exist."""
    output_dir = tmp_path / "site"
    output_dir.mkdir()
    mkdocs_path = output_dir / "mkdocs.yml"
    mkdocs_path.write_text(
        dedent(
            """
            site_name: Test
            docs_dir: docs
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Docs directory not found"):
        process_whatsapp_export(
            zip_path=tmp_path / "dummy.zip",
            output_dir=output_dir,
            enable_enrichment=False,
        )


def test_migrate_posts_with_placeholder_targets(tmp_path):
    """Legacy posts should be moved even when docs/posts holds scaffold files."""

    site_root = tmp_path / "site"
    docs_dir = site_root / "docs"
    legacy_posts = site_root / "posts"

    docs_posts = docs_dir / "posts"
    docs_posts.mkdir(parents=True)
    (docs_posts / "index.md").write_text("placeholder", encoding="utf-8")

    legacy_posts.mkdir(parents=True)
    legacy_file = legacy_posts / "2024-01-01-test.md"
    legacy_file.write_text("legacy content", encoding="utf-8")

    mkdocs_path = site_root / "mkdocs.yml"
    mkdocs_path.write_text("site_name: Test", encoding="utf-8")

    site_paths = resolve_site_paths(site_root)
    _migrate_legacy_structure(site_paths)

    migrated_post = docs_posts / legacy_file.name
    assert migrated_post.exists()
    assert migrated_post.read_text(encoding="utf-8") == "legacy content"
    assert not legacy_file.exists()


def test_migrate_media_merges_placeholder_directories(tmp_path):
    """Legacy media should merge into scaffold subdirectories like images/."""

    site_root = tmp_path / "site"
    docs_media = site_root / "docs" / "media"
    legacy_media = site_root / "media"

    images_target = docs_media / "images"
    images_target.mkdir(parents=True)
    (images_target / ".gitkeep").write_text("", encoding="utf-8")

    legacy_image_dir = legacy_media / "images"
    legacy_image_dir.mkdir(parents=True)
    legacy_image = legacy_image_dir / "photo.jpg"
    legacy_image.write_text("binary", encoding="utf-8")

    mkdocs_path = site_root / "mkdocs.yml"
    mkdocs_path.write_text("site_name: Test", encoding="utf-8")

    site_paths = resolve_site_paths(site_root)
    _migrate_legacy_structure(site_paths)

    migrated_image = images_target / legacy_image.name
    assert migrated_image.exists()
    assert migrated_image.read_text(encoding="utf-8") == "binary"
    assert not legacy_image.exists()
