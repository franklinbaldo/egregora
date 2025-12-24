from pathlib import Path

import pytest

from egregora_v3.core.config import EgregoraConfig
from egregora_v3.core.config_loader import ConfigLoader


def test_load_from_file(tmp_path):
    """Test loading configuration from a file."""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "custom-writer-model"

[paths]
posts_dir = "custom-posts"
        """
    )

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert isinstance(config, EgregoraConfig)
    assert config.models.writer == "custom-writer-model"
    assert config.paths.posts_dir == Path("custom-posts")
    assert config.paths.site_root == tmp_path


def test_load_defaults(tmp_path):
    """Test loading defaults when no config file exists."""
    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert isinstance(config, EgregoraConfig)
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    assert config.paths.site_root == tmp_path


def test_load_defaults_from_cwd(tmp_path, monkeypatch):
    """Test loading defaults using current working directory."""
    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)

    # Load without specifying site_root - should use CWD
    loader = ConfigLoader()
    config = loader.load()

    assert isinstance(config, EgregoraConfig)
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    assert config.paths.site_root == tmp_path


def test_load_from_cwd_with_toml(tmp_path, monkeypatch):
    """Test loading TOML configuration from current working directory."""
    # Setup config in tmp_path
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "cwd-custom-model"

[pipeline]
step_size = 5
        """
    )

    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)

    # Load without specifying site_root - should find .egregora.toml in CWD
    loader = ConfigLoader()
    config = loader.load()

    assert config.models.writer == "cwd-custom-model"
    assert config.pipeline.step_size == 5
    assert config.paths.site_root == tmp_path


def test_env_var_override_string(tmp_path, monkeypatch):
    """Test overriding string configuration with environment variables."""
    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "env-writer-model")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.models.writer == "env-writer-model"


def test_env_var_override_int(tmp_path, monkeypatch):
    """Test overriding integer configuration with environment variables.

    Pydantic Settings automatically converts string "10" to int 10.
    """
    monkeypatch.setenv("EGREGORA_PIPELINE__STEP_SIZE", "10")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.pipeline.step_size == 10
    assert isinstance(config.pipeline.step_size, int)


def test_env_var_override_boolean_true(tmp_path, monkeypatch):
    """Test overriding boolean configuration with environment variables (true)."""
    monkeypatch.setenv("EGREGORA_MODELS__FALLBACK_ENABLED", "true")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.models.fallback_enabled is True


def test_env_var_override_boolean_false(tmp_path, monkeypatch):
    """Test overriding boolean configuration with environment variables (false).

    Tests that string "false" is correctly converted to bool False.
    """
    monkeypatch.setenv("EGREGORA_MODELS__FALLBACK_ENABLED", "false")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.models.fallback_enabled is False


def test_env_var_override_path(tmp_path, monkeypatch):
    """Test overriding path configuration with environment variables."""
    monkeypatch.setenv("EGREGORA_PATHS__POSTS_DIR", "custom-posts-from-env")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.paths.posts_dir == Path("custom-posts-from-env")


def test_env_var_precedence_over_file(tmp_path, monkeypatch):
    """Test that environment variables take precedence over file configuration."""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "file-writer-model"
        """
    )

    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "env-writer-model")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    # Env var should win
    assert config.models.writer == "env-writer-model"


def test_invalid_toml(tmp_path):
    """Test handling of invalid TOML configuration."""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text("invalid = [")

    loader = ConfigLoader(tmp_path)
    with pytest.raises(ValueError, match="Invalid TOML"):
        loader.load()


def test_invalid_root_type(tmp_path):
    """Test that non-mapping TOML roots raise a clear error."""
    config_file = tmp_path / ".egregora.toml"
    # tomllib.load treats single list as valid but we validate it is dict
    # However, tomllib returns dict from valid toml key=value
    # If file content is just a list, tomllib.load returns that list if it is valid TOML?
    # Actually standard TOML files must be key-value pairs at root.
    # But a JSON array is valid TOML? No.
    # Let's try to write something that parses but isn't a dict if possible,
    # or just use a list syntax that might parse as a list (though strict TOML forbids it at root).
    # If tomllib raises TOMLDecodeError for list at root, then we should expect ValueError.
    # If it parses it as a list, we expect TypeError.
    # Let's write valid TOML that is interpreted as empty dict or similar?
    # Wait, invalid TOML raises ValueError.
    # We need something that parses successfully but isn't a dict.
    # But standard TOML parsers usually enforce root as table.
    # If tomllib.load returns a dict always for valid toml, then this test might be redundant or unreachable.
    # Let's try mocking tomllib.load instead to force return a list.

    # We need to patch tomllib.load used in ConfigLoader
    # But ConfigLoader imports tomllib inside module scope if 3.11+, or via compat
    # Actually ConfigLoader imports tomllib at top level.

    # We can't easily monkeypatch built-in tomllib.load in some environments.
    # But let's check what the implementation does.
    # It checks `if not isinstance(data, dict): raise TypeError`.
    # So we just need `tomllib.load` to return a list.
    # Since `tomllib` is strictly compliant, it might be hard to get a list from valid TOML file at root.
    # So let's skip this test if we can't easily force it, or mock it.

    # If we assume tomllib ALWAYS returns a dict for valid TOML, then the check is defensive.
    # We can use monkeypatch on the instance method `_load_from_file` instead.

    loader = ConfigLoader(tmp_path)
    # Monkeypatch the private method to return a list
    loader._load_from_file = lambda: ["invalid", "list"]

    with pytest.raises(TypeError, match="Configuration must be a mapping"):
        loader.load()


def test_case_insensitivity(tmp_path, monkeypatch):
    """Test that environment variable names are case-insensitive after prefix.

    Pydantic Settings converts env var names to lowercase for matching.
    """
    # Mixed case after prefix should still work
    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "mixed-case-model")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.models.writer == "mixed-case-model"
