"""Guardrails that enforce release hygiene for the project."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_project_version() -> str:
    """Read the canonical project version from ``pyproject.toml``."""

    pyproject = PROJECT_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text("utf-8"))
    return data["project"]["version"]


def test_package_version_matches_pyproject() -> None:
    """Ensure the distributed package reports the same version as the project."""

    package_init = PROJECT_ROOT / "src" / "egregora" / "__init__.py"
    init_contents = package_init.read_text("utf-8")

    match = re.search(r"__version__\s*=\s*\"([^\"]+)\"", init_contents)
    assert match, "Could not determine __version__ from src/egregora/__init__.py"

    package_version = match.group(1)
    assert (
        package_version == _load_project_version()
    ), "__version__ must match project.version in pyproject.toml"


def test_changelog_mentions_current_version() -> None:
    """Fail if the changelog lacks a section for the current release."""

    changelog = PROJECT_ROOT / "CHANGELOG.md"
    changelog_text = changelog.read_text("utf-8")
    version = _load_project_version()

    # Require a changelog heading such as ``## [1.2.3]`` or ``## [1.2.3] - YYYY-MM-DD``.
    heading_pattern = re.compile(rf"^## \[{re.escape(version)}](?:\s+-\s+.+)?$", re.MULTILINE)

    assert heading_pattern.search(
        changelog_text
    ), "CHANGELOG.md must contain a heading for the current version"


def test_docs_reference_current_version() -> None:
    """Fail when the public documentation does not mention the current version."""

    docs_readme = PROJECT_ROOT / "docs" / "README.md"
    docs_text = docs_readme.read_text("utf-8")

    assert (
        _load_project_version() in docs_text
    ), "docs/README.md must reference the current release version"
