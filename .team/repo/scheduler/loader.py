"""Persona loading and prompt rendering for Jules scheduler."""

import sys
import uuid
from pathlib import Path
from typing import Any

import frontmatter
import jinja2

from repo.scheduler.models import PersonaConfig


class PersonaLoader:
    """Loads and renders persona prompts using Jinja2 template inheritance."""

    def __init__(self, personas_dir: Path, base_context: dict[str, Any] | None = None):
        """Initialize loader with Jinja2 environment.

        Args:
            personas_dir: Path to .team/personas directory
            base_context: Base template context (repo info, etc.)
        """
        self.personas_dir = personas_dir
        self.base_context = base_context or {}
        self.templates_dir = Path(__file__).parent.parent / "templates"

        # Single Jinja environment with proper loader chain
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader([
                str(self.templates_dir),  # For base templates and blocks
                str(personas_dir),         # For persona-specific templates
            ]),
            undefined=jinja2.Undefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def load_personas(self, cycle_list: list[str]) -> list[PersonaConfig]:
        """Load all personas, optionally filtered by cycle list.

        Args:
            cycle_list: If provided, load only these personas in order.
                       If empty, discover and load all personas.

        Returns:
            List of PersonaConfig objects.
        """
        if cycle_list:
            return self._load_from_cycle_list(cycle_list)
        return self._discover_all_personas()

    def _load_from_cycle_list(self, cycle_list: list[str]) -> list[PersonaConfig]:
        """Load personas from explicit cycle list."""
        configs = []
        base_dir = self.personas_dir.parent

        for rel_path in cycle_list:
            prompt_file = self._resolve_prompt_path(base_dir / rel_path)
            if not prompt_file:
                print(f"Prompt not found: {rel_path}", file=sys.stderr)
                continue

            try:
                configs.append(self.load_persona(prompt_file))
            except Exception as e:
                print(f"Failed to load {rel_path}: {e}", file=sys.stderr)

        return configs

    def _discover_all_personas(self) -> list[PersonaConfig]:
        """Discover and load all personas from directory."""
        # Find all prompt files, preferring .j2 over .md
        found = {}
        for pattern in ["*/prompt.md.j2", "*/prompt.md"]:
            for path in self.personas_dir.glob(pattern):
                name = path.parent.name
                if name not in found or path.suffix == ".j2":
                    found[name] = path

        configs = []
        for prompt_file in sorted(found.values()):
            try:
                configs.append(self.load_persona(prompt_file))
            except Exception as e:
                print(f"Failed to load {prompt_file}: {e}", file=sys.stderr)

        return configs

    def _resolve_prompt_path(self, base_path: Path) -> Path | None:
        """Resolve prompt file path with extension fallbacks."""
        candidates = [
            base_path,
            base_path.with_suffix(".md.j2"),
            base_path.with_suffix(".j2"),
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def load_persona(self, prompt_file: Path) -> PersonaConfig:
        """Load a single persona configuration.

        Args:
            prompt_file: Path to persona's prompt.md.j2 file

        Returns:
            PersonaConfig with rendered prompt

        Raises:
            ValueError: If persona missing required 'id' field
        """
        persona_dir = prompt_file.parent
        post = frontmatter.load(prompt_file)

        persona_id = post.metadata.get("id")
        if not persona_id:
            raise ValueError(f"Missing 'id' in {prompt_file}")

        emoji = post.metadata.get("emoji", "")
        description = post.metadata.get("description", "")

        # Ensure journals directory exists
        (persona_dir / "journals").mkdir(parents=True, exist_ok=True)

        # Build context for template rendering
        journal_entries = self._collect_journals(persona_dir)
        context = self._build_context(persona_id, emoji, journal_entries, post.metadata)

        # Render the prompt template
        prompt_body = self._render_template(post.content, context)

        return PersonaConfig(
            id=persona_id,
            emoji=emoji,
            description=description,
            prompt_body=prompt_body,
            journal_entries=journal_entries,
            path=str(prompt_file),
        )

    def _build_context(
        self,
        persona_id: str,
        emoji: str,
        journal_entries: str,
        metadata: dict,
    ) -> dict[str, Any]:
        """Build the template rendering context."""
        return {
            # Base context (repo info, open PRs, etc.)
            **self.base_context,
            # Frontmatter metadata
            **metadata,
            # Persona-specific
            "id": persona_id,
            "emoji": emoji,
            "journal_entries": journal_entries,
            # Generated values
            "password": str(uuid.uuid5(uuid.NAMESPACE_DNS, persona_id)),
        }

    def _render_template(self, template_content: str, context: dict) -> str:
        """Render a Jinja2 template string with full inheritance support.

        The template can use {% extends %} and {% include %} directives
        which will be resolved through the Jinja environment's loader.
        """
        template = self.jinja_env.from_string(template_content)
        return template.render(**context).strip()

    def _collect_journals(self, persona_dir: Path, limit: int = 10) -> str:
        """Collect recent journal entries for context.

        Args:
            persona_dir: Path to persona directory
            limit: Maximum number of entries to include

        Returns:
            Formatted string with journal entries
        """
        journals_dir = persona_dir / "journals"
        if not journals_dir.exists():
            return ""

        journal_files = sorted(journals_dir.glob("*.md"))[-limit:]

        entries = []
        for journal_file in journal_files:
            try:
                content = journal_file.read_text().strip()
                # Strip frontmatter if present
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                if content:
                    entries.append(f"--- {journal_file.name} ---\n{content}")
            except Exception:
                pass

        return "\n\n".join(entries)
