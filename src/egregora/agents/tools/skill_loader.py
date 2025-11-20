"""Skill loading utilities for agent skill injection.

This module provides functionality to load and parse skill content from the
.egregora/skills/ directory, enabling agents to dynamically extend their
capabilities at runtime.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Safe skill name pattern: alphanumeric, hyphens, underscores only
_SAFE_SKILL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class SkillContent:
    """Parsed skill content with metadata."""

    name: str
    """Skill identifier (filename without extension)."""

    content: str
    """Full skill content/instructions."""

    description: str | None
    """Optional short description extracted from content."""

    source_path: Path
    """Path to the skill file."""


class SkillLoader:
    """Loads skills from the .egregora/skills/ directory."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        """Initialize skill loader.

        Args:
            skills_dir: Path to skills directory. If None, will search for
                       .egregora/skills/ in current directory or parents.

        """
        self.skills_dir = skills_dir or self._find_skills_dir()

    def _find_skills_dir(self) -> Path:
        """Find .egregora/skills/ directory by walking up from current dir."""
        current = Path.cwd()
        while current != current.parent:
            candidate = current / ".egregora" / "skills"
            if candidate.exists() and candidate.is_dir():
                return candidate
            current = current.parent

        # Fallback: create in current directory
        fallback = Path.cwd() / ".egregora" / "skills"
        logger.warning("No .egregora/skills/ directory found, will use: %s", fallback)
        return fallback

    def _validate_skill_name(self, skill_name: str) -> None:
        """Validate skill name to prevent directory traversal attacks.

        Args:
            skill_name: Skill name to validate.

        Raises:
            ValueError: If skill name contains unsafe characters or path separators.

        """
        # Check for empty name
        if not skill_name or not skill_name.strip():
            msg = "Skill name cannot be empty"
            raise ValueError(msg)

        # Check for unsafe characters (prevent directory traversal)
        if not _SAFE_SKILL_NAME_PATTERN.match(skill_name):
            msg = (
                f"Invalid skill name: '{skill_name}'. "
                "Skill names must contain only alphanumeric characters, hyphens, and underscores."
            )
            raise ValueError(msg)

        # Additional safety: check for path separators (should be caught by pattern, but be explicit)
        if "/" in skill_name or "\\" in skill_name or ".." in skill_name:
            msg = f"Skill name cannot contain path separators or parent directory references: '{skill_name}'"
            raise ValueError(msg)

    def load_skill(self, skill_name: str) -> SkillContent:
        """Load a skill by name.

        Args:
            skill_name: Name of the skill (without extension).
                       Must contain only alphanumeric characters, hyphens, and underscores.

        Returns:
            Parsed skill content.

        Raises:
            FileNotFoundError: If skill file doesn't exist.
            ValueError: If skill name is invalid or skill content is empty.

        """
        # Validate skill name to prevent directory traversal
        self._validate_skill_name(skill_name)

        # Try common extensions
        for ext in [".md", ".txt", ".skill"]:
            skill_path = self.skills_dir / f"{skill_name}{ext}"

            # Double-check: ensure resolved path is within skills_dir
            # (defense in depth - pattern check should prevent this, but verify)
            try:
                skill_path_resolved = skill_path.resolve()
                skills_dir_resolved = self.skills_dir.resolve()
                if not skill_path_resolved.is_relative_to(skills_dir_resolved):
                    msg = f"Security violation: skill path escapes skills directory: {skill_name}"
                    raise ValueError(msg)
            except ValueError as exc:
                # is_relative_to raises ValueError if path is not relative
                msg = f"Security violation: skill path escapes skills directory: {skill_name}"
                raise ValueError(msg) from exc

            if skill_path.exists():
                break
        else:
            msg = f"Skill '{skill_name}' not found in {self.skills_dir}. Tried extensions: .md, .txt, .skill"
            raise FileNotFoundError(msg)

        content = skill_path.read_text(encoding="utf-8").strip()
        if not content:
            msg = f"Skill file is empty: {skill_path}"
            raise ValueError(msg)

        # Extract description from first paragraph or heading
        description = self._extract_description(content)

        logger.info("Loaded skill: %s from %s (%d chars)", skill_name, skill_path, len(content))

        return SkillContent(
            name=skill_name,
            content=content,
            description=description,
            source_path=skill_path,
        )

    def list_available_skills(self) -> list[str]:
        """List all available skill names.

        Returns:
            List of skill names (without extensions).

        """
        if not self.skills_dir.exists():
            return []

        skills = set()
        for ext in [".md", ".txt", ".skill"]:
            for path in self.skills_dir.glob(f"*{ext}"):
                skills.add(path.stem)

        return sorted(skills)

    def _extract_description(self, content: str) -> str | None:
        """Extract a short description from skill content.

        Looks for:
        1. First markdown heading (# Description)
        2. First paragraph
        3. First non-empty line

        Args:
            content: Skill content.

        Returns:
            Description or None.

        """
        lines = content.strip().split("\n")
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue
            # Return first substantial line (>10 chars)
            min_len = 10
            if len(stripped_line) > min_len:
                return stripped_line[:200]  # Truncate at 200 chars
        return None


# Singleton instance for convenience
_default_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    """Get the default global skill loader instance."""
    global _default_loader  # noqa: PLW0603
    if _default_loader is None:
        _default_loader = SkillLoader()
    return _default_loader
