#!/usr/bin/env python3
"""
Pre-commit hook to validate persona prompt changes.

Rules:
1. Personas can hire new personas (create new prompt files)
2. Personas can modify their OWN prompt.md.j2
3. Personas CANNOT modify other personas' prompts

The active persona is determined by checking the current session.
"""

import subprocess
import sys
from pathlib import Path

# Add .team to path for imports
sys.path.insert(0, ".team")


def get_active_persona() -> str | None:
    """Get the currently active persona from session."""
    try:
        from repo.features.session import SessionManager

        sm = SessionManager()
        return sm.get_active_persona()
    except Exception:
        return None


def get_staged_prompt_files() -> list[Path]:
    """Get list of staged .j2 prompt files in personas directory."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACDMR"], capture_output=True, text=True
    )
    if result.returncode != 0:
        return []

    files = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        path = Path(line)
        # Check if it's a persona prompt file
        if ".team/personas/" in str(path) and path.name.endswith(".j2"):
            files.append(path)
    return files


def get_persona_from_path(path: Path) -> str | None:
    """Extract persona ID from a path like .team/personas/<id>/prompt.md.j2"""
    parts = path.parts
    try:
        personas_idx = parts.index("personas")
        if personas_idx + 1 < len(parts):
            return parts[personas_idx + 1]
    except ValueError:
        pass
    return None


def is_new_file(path: Path) -> bool:
    """Check if file is newly added (not modified)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"], capture_output=True, text=True
    )
    return str(path) in result.stdout


def main():
    staged_prompts = get_staged_prompt_files()
    if not staged_prompts:
        # No prompt files changed, nothing to validate
        return 0

    active_persona = get_active_persona()

    violations = []
    for path in staged_prompts:
        target_persona = get_persona_from_path(path)

        if target_persona is None:
            continue

        # New files are allowed (hiring new personas)
        if is_new_file(path):
            print(f"✅ New persona file allowed: {path}")
            continue

        # Modifying own prompt is allowed
        if active_persona and target_persona == active_persona:
            print(f"✅ Self-modification allowed: {path}")
            continue

        # Modifying another persona's prompt is NOT allowed
        violations.append(
            {
                "path": path,
                "target_persona": target_persona,
                "active_persona": active_persona or "(no session)",
            }
        )

    if violations:
        print("\n❌ PROMPT MODIFICATION VIOLATION")
        print("=" * 50)
        print("Personas can only modify their OWN prompts.\n")
        for v in violations:
            print(f"  File: {v['path']}")
            print(f"  Target persona: {v['target_persona']}")
            print(f"  Active persona: {v['active_persona']}")
            print()
        print("To modify another persona's prompt, you must:")
        print("1. Login as that persona, OR")
        print("2. Request they make the change themselves")
        print("=" * 50)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
