from pathlib import Path

from egregora.pipeline import _migrate_directory


def test_migrate_directory_moves_when_target_has_placeholders(tmp_path: Path) -> None:
    site_root = tmp_path
    legacy_posts = site_root / "posts"
    legacy_posts.mkdir()
    (legacy_posts / "post1.md").write_text("content", encoding="utf-8")

    target_dir = site_root / "docs" / "posts"
    target_dir.mkdir(parents=True)
    (target_dir / ".gitkeep").write_text("", encoding="utf-8")

    _migrate_directory(legacy_posts, target_dir, "posts")

    assert not legacy_posts.exists()
    assert (target_dir / "post1.md").exists()
    assert (target_dir / ".gitkeep").exists()
