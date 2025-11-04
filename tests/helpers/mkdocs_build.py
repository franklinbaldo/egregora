import shutil
import subprocess
import tempfile
from pathlib import Path


def run_mkdocs_build(site_dir):
    """Runs the mkdocs build command in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copytree(site_dir, tmpdir, dirs_exist_on_ok=True)
        subprocess.run(["mkdocs", "build"], cwd=tmpdir, check=True)
        return Path(tmpdir) / "site"
