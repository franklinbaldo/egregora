"""
E2E test to ensure the `egregora demo` command generates a valid, buildable site.
"""
import subprocess
import sys
from pathlib import Path

import pytest


def test_demo_command_generates_a_buildable_site(tmp_path: Path):
    """
    Verifies that `egregora demo` command:
    1. Creates the expected directory structure.
    2. Produces a site that can be successfully built by MkDocs.
    """
    demo_site_path = tmp_path / "demo_site"
    demo_site_path.mkdir()

    # Generate a fresh demo site into the temporary directory.
    generate_command = [
        "uv",
        "run",
        "egregora",
        "demo",
        "--output-dir",
        str(demo_site_path),
    ]
    try:
        subprocess.run(
            generate_command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        pytest.skip("Could not find 'uv' command. Is it installed and in PATH?")
    except subprocess.CalledProcessError as e:
        pytest.fail(
            "Failed to generate demo site.\\n"
            f"Stderr: {e.stderr}\\nStdout: {e.stdout}"
        )

    # 1. Verify that essential files and directories were created.
    assert (demo_site_path / ".egregora" / "mkdocs.yml").exists(), "mkdocs.yml is missing."
    assert (demo_site_path / "docs").is_dir(), "'docs/' directory is missing."
    assert (
        demo_site_path / "docs" / "posts"
    ).is_dir(), "'docs/posts/' directory is missing."

    # 2. Attempt to build the site using MkDocs to ensure it's valid.
    build_command = [
        sys.executable,
        "-m",
        "mkdocs",
        "build",
        "-f",
        str(demo_site_path / ".egregora" / "mkdocs.yml"),
    ]

    result = subprocess.run(
        build_command,
        check=False,
        capture_output=True,
        text=True,
        cwd=demo_site_path,
    )

    # The test passes if the build command returns 0 (success).
    # We check the stderr for "not installed" to provide a more helpful
    # message in environments where MkDocs plugins might be missing.
    if "not installed" in result.stderr:
        pytest.skip(f"A required MkDocs plugin is not installed: {result.stderr}")

    assert result.returncode == 0, (
        "The generated demo site failed to build with MkDocs.\\n"
        f"Stderr: {result.stderr}\\nStdout: {result.stdout}"
    )
