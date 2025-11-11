"""Skill loading utilities for agent skill injection.

This module provides functionality to load and parse skill content from the
.egregora/skills/ directory, enabling agents to dynamically extend their
capabilities at runtime.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


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
        logger.warning(
            f"No .egregora/skills/ directory found, will use: {fallback}"
        )
        return fallback

    def load_skill(self, skill_name: str) -> SkillContent:
        """Load a skill by name.

        Args:
            skill_name: Name of the skill (without extension).

        Returns:
            Parsed skill content.

        Raises:
            FileNotFoundError: If skill file doesn't exist.
            ValueError: If skill content is empty.

        """
        # Try common extensions
        for ext in [".md", ".txt", ".skill"]:
            skill_path = self.skills_dir / f"{skill_name}{ext}"
            if skill_path.exists():
                break
        else:
            msg = (
                f"Skill '{skill_name}' not found in {self.skills_dir}. "
                f"Tried extensions: .md, .txt, .skill"
            )
            raise FileNotFoundError(
                msg
            )

        content = skill_path.read_text(encoding="utf-8").strip()
        if not content:
            msg = f"Skill file is empty: {skill_path}"
            raise ValueError(msg)

        # Extract description from first paragraph or heading
        description = self._extract_description(content)

        logger.info(
            f"Loaded skill: {skill_name} from {skill_path} "
            f"({len(content)} chars)"
        )

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
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Return first substantial line (>10 chars)
            if len(line) > 10:
                return line[:200]  # Truncate at 200 chars
        return None


# Singleton instance for convenience
_default_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    """Get the default global skill loader instance."""
    global _default_loader
    if _default_loader is None:
        _default_loader = SkillLoader()
    return _default_loader
