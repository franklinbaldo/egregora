import pytest
from pathlib import Path
from egregora_v3.core.config import EgregoraConfig


@pytest.fixture
def chdir_tmp(tmp_path: Path, monkeypatch):
    """Fixture to change the current working directory to a temporary directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_egregora_config_loads_from_toml_in_cwd(chdir_tmp: Path):
    """Test that EgregoraConfig loads from a .egregora.toml file in the current working directory."""
    config_content = """
    [models]
    writer = "test-writer"

    [paths]
    site_root = "."
    """
    (chdir_tmp / ".egregora.toml").write_text(config_content)
    config = EgregoraConfig()
    assert config.models.writer == "test-writer"
    assert config.paths.site_root == chdir_tmp.resolve()


def test_egregora_config_uses_cwd_as_default_site_root(chdir_tmp: Path):
    """Test that EgregoraConfig defaults to the current working directory for site_root."""
    config = EgregoraConfig()
    assert config.paths.site_root == chdir_tmp.resolve()
