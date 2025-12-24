
from pathlib import Path
from egregora_v3.core.config import EgregoraConfig, PathsSettings

def test_declarative_load_from_toml(tmp_path, monkeypatch):
    """Test that EgregoraConfig loads from .egregora.toml in the CWD declaratively."""
    # Setup a mock site
    site_root = tmp_path / "mysite"
    site_root.mkdir(parents=True)

    config_file = site_root / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "declarative-model"

[paths]
posts_dir = "content/blog"
"""
    )

    # Change to site directory
    monkeypatch.chdir(site_root)

    # This instantiation should fail to load the config until the main code is refactored
    config = EgregoraConfig()

    assert config.models.writer == "declarative-model"
    assert config.paths.site_root == site_root
    assert config.paths.posts_dir == Path("content/blog")
    assert config.paths.abs_posts_dir == site_root / "content/blog"

def test_env_var_override(tmp_path, monkeypatch):
    """Test that environment variables override TOML settings."""
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

    config = EgregoraConfig()

    assert config.models.writer == "env-var-model"
