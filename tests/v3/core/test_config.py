from pathlib import Path
import os
import pytest
from egregora_v3.core.config import EgregoraConfig

def test_config_loading_post_refactor(tmp_path: Path):
    """
    Test that EgregoraConfig correctly loads configuration using
    pydantic-settings's declarative TOML loading.
    """
    # 1. Create a dummy config file in the temp path
    config_content = """
[models]
writer = "toml-writer-model"
enricher = "toml-enricher-model"
"""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(config_content)

    # 2. Set environment variables
    os.environ["EGREGORA_MODELS__WRITER"] = "env-writer-model"
    os.environ["EGREGORA_PATHS__POSTS_DIR"] = "env/posts"

    # 3. Change working directory to tmp_path to simulate running from site root
    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        # 4. Load the config (pydantic-settings finds it automatically)
        config = EgregoraConfig()

        # 5. Assertions
        # Env var should override TOML
        assert config.models.writer == "env-writer-model"
        # Value from TOML
        assert config.models.enricher == "toml-enricher-model"
        # Default value
        assert config.models.embedding == "models/gemini-embedding-001"
        # Env var for a different section
        assert config.paths.posts_dir == Path("env/posts")
        # site_root should default to the current working directory (tmp_path)
        assert config.paths.site_root == tmp_path

    finally:
        # 6. Clean up environment variables and restore CWD
        os.chdir(original_cwd)
        del os.environ["EGREGORA_MODELS__WRITER"]
        del os.environ["EGREGORA_PATHS__POSTS_DIR"]


def test_paths_settings_resolve(tmp_path: Path):
    """
    Test the PathSettings.resolve method for both relative and absolute paths.
    """
    # 1. Create a config with site_root set to a temporary directory
    config = EgregoraConfig(paths={"site_root": tmp_path})
    paths_settings = config.paths

    # 2. Test resolving a relative path
    relative_path = Path("posts")
    expected_abs_path = tmp_path / "posts"
    assert paths_settings.resolve(relative_path) == expected_abs_path

    # 3. Test resolving an absolute path
    absolute_path = Path("/etc/passwd")
    assert paths_settings.resolve(absolute_path) == absolute_path
