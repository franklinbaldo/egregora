from pathlib import Path
from egregora_v3.core.config import EgregoraConfig, PathsSettings


def test_default_config(tmp_path, monkeypatch):
    """Test default configuration uses current working directory."""
    monkeypatch.chdir(tmp_path)
    config = EgregoraConfig()
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    assert config.paths.site_root == tmp_path.resolve()


def test_path_resolution(tmp_path):
    site_root = tmp_path / "mysite"
    site_root.mkdir()
    paths = PathsSettings(site_root=site_root, posts_dir=Path("content/posts"))

    assert paths.abs_posts_dir == site_root / "content/posts"
    assert paths.abs_db_path == site_root / ".egregora/pipeline.duckdb"


def test_load_from_toml(tmp_path, monkeypatch):
    # Setup a mock site
    site_root = tmp_path / "mysite"
    site_root.mkdir(parents=True)

    config_file = site_root / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "custom-model"
        """
    )
    monkeypatch.chdir(site_root)

    # Load config
    config = EgregoraConfig()

    assert config.models.writer == "custom-model"
    assert config.paths.site_root == site_root.resolve()
    assert config.paths.abs_posts_dir == site_root.resolve() / "posts"

    # Change to site directory
    monkeypatch.chdir(site_root)

def test_load_missing_file(tmp_path, monkeypatch):
    """Test loading from directory without config file."""
    site_root = tmp_path / "empty_site"
    site_root.mkdir()
    monkeypatch.chdir(site_root)

    config = EgregoraConfig()
    assert config.models.writer == "google-gla:gemini-2.0-flash"  # Default
    assert config.paths.site_root == site_root.resolve()


def test_load_from_cwd(tmp_path, monkeypatch):
    """Test loading from current working directory."""
    site_root = tmp_path / "mysite"
    site_root.mkdir(parents=True)

    config_file = site_root / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "toml-model"
"""
    )

    monkeypatch.chdir(site_root)
    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "env-var-model")

    # Load - should use CWD as project root
    config = EgregoraConfig()
    assert config.models.writer == "cwd-model"
    assert config.paths.site_root == site_root.resolve()
