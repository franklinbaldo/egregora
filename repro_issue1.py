from pathlib import Path
from egregora_v3.core.config import PathsSettings, EgregoraConfig

def test_site_root_behavior():
    # Case 1: Default initialization
    config = EgregoraConfig()
    print(f"Default config.paths.site_root: {config.paths.site_root}")
    resolved = config.paths.abs_posts_dir
    print(f"Resolved posts_dir: {resolved}")
    print(f"CWD: {Path.cwd()}")

    # Verify it matches CWD
    assert resolved == Path.cwd() / "posts"
    print("Assertion passed: Defaults to CWD")

if __name__ == "__main__":
    test_site_root_behavior()
