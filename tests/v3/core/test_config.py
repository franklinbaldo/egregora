import pytest
from pathlib import Path
import yaml
from egregora_v3.core.config import EgregoraConfig, PathsSettings

def test_default_config():
    config = EgregoraConfig()
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    assert config.pipeline.step_unit == "days"
    assert config.paths.site_root == Path(".")

def test_path_resolution():
    site_root = Path("/tmp/mysite")
    paths = PathsSettings(site_root=site_root, posts_dir=Path("content/posts"))

    assert paths.abs_posts_dir == Path("/tmp/mysite/content/posts")
    assert paths.abs_db_path == Path("/tmp/mysite/.egregora/pipeline.duckdb")

def test_load_from_yaml(tmp_path):
    # Setup a mock site
    site_root = tmp_path / "mysite"
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(parents=True)

    config_data = {
        "pipeline": {
            "step_size": 7,
            "step_unit": "days"
        },
        "models": {
            "writer": "custom-model"
        }
    }

    with open(egregora_dir / "config.yml", "w") as f:
        yaml.dump(config_data, f)

    # Load config
    config = EgregoraConfig.load(site_root)

    assert config.pipeline.step_size == 7
    assert config.models.writer == "custom-model"
    assert config.paths.site_root == site_root
    assert config.paths.abs_posts_dir == site_root / "posts"

def test_load_missing_file(tmp_path):
    site_root = tmp_path / "empty_site"
    site_root.mkdir()

    config = EgregoraConfig.load(site_root)
    assert config.pipeline.step_size == 1  # Default
    assert config.paths.site_root == site_root
