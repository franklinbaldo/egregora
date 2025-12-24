from pathlib import Path

from egregora_v3.core.config import EgregoraConfig, PathsSettings


def test_default_config():
    """Test default configuration uses current working directory."""
    config = EgregoraConfig()
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    # site_root defaults to CWD
    assert config.paths.site_root == Path.cwd()


def test_path_resolution(tmp_path):
    site_root = tmp_path / "mysite"
    paths = PathsSettings(site_root=site_root, posts_dir=Path("content/posts"))

    assert paths.abs_posts_dir == site_root / "content/posts"
    assert paths.abs_db_path == site_root / ".egregora/pipeline.duckdb"


def test_load_from_toml(tmp_path):
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

    # Load config
    config = EgregoraConfig.load(site_root)

    assert config.models.writer == "custom-model"
    assert config.paths.site_root == site_root
    assert config.paths.abs_posts_dir == site_root / "posts"


def test_load_missing_file(tmp_path):
    """Test loading from directory without config file (explicit path)."""
    site_root = tmp_path / "empty_site"
    site_root.mkdir()

    config = EgregoraConfig.load(site_root)
    assert config.models.writer == "google-gla:gemini-2.0-flash"  # Default
    assert config.paths.site_root == site_root


def test_load_from_cwd(tmp_path, monkeypatch):
    """Test loading from current working directory (no explicit path)."""
    site_root = tmp_path / "mysite"
    site_root.mkdir(parents=True)

    config_file = site_root / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "cwd-model"
        """
    )

    # Change to site directory
    monkeypatch.chdir(site_root)

    # Load without path - should use CWD
    config = EgregoraConfig.load()
    assert config.models.writer == "cwd-model"
    assert config.paths.site_root == site_root


def test_env_overrides_toml(tmp_path, monkeypatch):
    """Verify that environment variables take precedence over the TOML file."""
    site_root = tmp_path / "mysite"
    site_root.mkdir(parents=True)

    config_file = site_root / ".egregora.toml"
    config_file.write_text('[models]\nwriter = "toml-writer"\n')

    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "env-writer")

    config = EgregoraConfig.load(site_root)

    assert config.models.writer == "env-writer"
