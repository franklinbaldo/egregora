#!/usr/bin/env python3
"""Verify egregora directory structure is correct after tree restructuring."""

from __future__ import annotations

import sys
from pathlib import Path


def check_structure() -> list[str]:
    """Check directory structure and return list of errors."""
    errors = []

    # No tests_unit/ directory
    if Path("tests_unit").exists():
        errors.append("tests_unit/ should not exist (consolidated into tests/)")

    # No egregora/egregora/ directory
    if Path("egregora/egregora").exists():
        errors.append("egregora/egregora/ should not exist")

    # No .jinja2 files in src/
    jinja2_files = list(Path("src").rglob("*.jinja2"))
    if jinja2_files:
        errors.append(f"Found .jinja2 files (should be .jinja): {[str(f) for f in jinja2_files]}")

    # Test structure exists
    required_test_dirs = [
        "tests/unit",
        "tests/integration",
        "tests/e2e",
        "tests/agents",
        "tests/linting",
        "tests/fixtures",
        "tests/utils",
    ]
    for test_dir in required_test_dirs:
        if not Path(test_dir).exists():
            errors.append(f"Missing {test_dir}/")

    # Prompt structure exists
    required_prompt_dirs = [
        "src/egregora/prompts/system",
        "src/egregora/prompts/enrichment",
    ]
    for prompt_dir in required_prompt_dirs:
        if not Path(prompt_dir).exists():
            errors.append(f"Missing {prompt_dir}/")

    # Check for renamed agent files
    old_agent_files = [
        "src/egregora/generation/editor/pydantic_agent.py",
        "src/egregora/generation/writer/pydantic_agent.py",
        "src/egregora/knowledge/ranking/pydantic_agent.py",
    ]
    for old_file in old_agent_files:
        if Path(old_file).exists():
            errors.append(f"Old file {old_file} still exists (should be renamed)")

    # Check for new agent files
    new_agent_files = [
        "src/egregora/generation/editor/editor_agent.py",
        "src/egregora/generation/writer/writer_agent.py",
        "src/egregora/knowledge/ranking/ranking_agent.py",
    ]
    for new_file in new_agent_files:
        if not Path(new_file).exists():
            errors.append(f"New file {new_file} not found")

    # Root documentation - should only have essential files
    essential_root_docs = {
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "LICENSE",
    }
    root_md_files = {f.name for f in Path().glob("*.md")}
    extra_docs = root_md_files - essential_root_docs
    if extra_docs:
        errors.append(f"Extra docs in root (should be in docs/): {extra_docs}")

    # Check dev_tools/ exists
    if not Path("dev_tools").exists():
        errors.append("dev_tools/ directory not found")

    # Check old scripts/ and tools/ are gone
    if Path("scripts").exists() and list(Path("scripts").iterdir()):
        errors.append("scripts/ should be empty or removed (use dev_tools/)")
    if Path("tools").exists() and list(Path("tools").iterdir()):
        errors.append("tools/ should be empty or removed (use dev_tools/)")

    return errors


def main() -> int:
    """Run structure verification."""
    errors = check_structure()

    if errors:
        for _error in errors:
            pass
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
