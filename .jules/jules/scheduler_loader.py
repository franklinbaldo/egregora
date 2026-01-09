"""Persona loading and prompt parsing for Jules scheduler."""

import sys
from pathlib import Path
from typing import Any

import frontmatter
import jinja2

from jules.scheduler_models import PersonaConfig


class PersonaLoader:
    """Loads and parses persona configurations from .jules/personas/."""

    def __init__(self, personas_dir: Path, base_context: dict[str, Any]):
        """Initialize loader.

        Args:
            personas_dir: Path to .jules/personas directory
            base_context: Base template context (repo info, etc.)
        """
        self.personas_dir = personas_dir
        self.base_context = base_context
        self.jinja_env = jinja2.Environment()

    def load_personas(self, cycle_list: list[str]) -> list[PersonaConfig]:
        """Load all personas in cycle order.

        Args:
            cycle_list: Ordered list of relative paths (e.g., ["personas/curator/prompt.md"])
                       If empty, loads all personas from directory

        Returns:
            List of PersonaConfig in cycle order

        Raises:
            SystemExit: If cycle_list is provided but no valid prompts found
        """
        configs: list[PersonaConfig] = []

        if cycle_list:
            # Load specific personas in cycle order
            base_dir = self.personas_dir.parent
            for rel_path in cycle_list:
                prompt_file = (base_dir / rel_path).resolve()
                if not prompt_file.exists():
                    print(f"Cycle prompt not found: {rel_path}", file=sys.stderr)
                    continue

                try:
                    config = self.load_persona(prompt_file)
                    configs.append(config)
                except Exception as exc:
                    print(f"Failed to load cycle prompt {rel_path}: {exc}", file=sys.stderr)

            if not configs:
                print("Cycle list provided but no valid prompts were loaded.", file=sys.stderr)
                sys.exit(1)
        else:
            # Load all personas from directory
            for prompt_file in sorted(self.personas_dir.glob("*/prompt.md")):
                try:
                    config = self.load_persona(prompt_file)
                    configs.append(config)
                except Exception as exc:
                    print(f"Failed to load {prompt_file}: {exc}", file=sys.stderr)

        return configs

    def load_persona(self, prompt_file: Path) -> PersonaConfig:
        """Load a single persona configuration.

        Args:
            prompt_file: Path to persona's prompt.md file

        Returns:
            PersonaConfig with all fields populated

        Raises:
            ValueError: If persona is missing required fields
            OSError: If file cannot be read
        """
        persona_dir = prompt_file.parent
        post = frontmatter.load(prompt_file)

        # Extract metadata
        persona_id = post.metadata.get("id")
        emoji = post.metadata.get("emoji", "")
        description = post.metadata.get("description", "")

        if not persona_id:
            raise ValueError(f"Persona at {prompt_file} is missing 'id' field")

        # Ensure journals directory exists
        self._ensure_journals_directory(persona_dir)

        # Collect journal entries for context
        journal_entries = self._collect_journals(persona_dir)

        # Build template context
        context = {
            **self.base_context,
            "journal_entries": journal_entries,
            "emoji": emoji,
            "id": persona_id,
        }

        # Parse prompt body with Jinja2
        prompt_body = self._render_prompt(post.content, post.metadata, context)

        return PersonaConfig(
            id=persona_id,
            emoji=emoji,
            description=description,
            prompt_body=prompt_body,
            journal_entries=journal_entries,
            path=str(prompt_file),
        )

    def _render_prompt(self, body_template: str, metadata: dict, context: dict) -> str:
        """Render prompt template with context.

        Args:
            body_template: Raw prompt text with Jinja2 templates
            metadata: Persona frontmatter
            context: Template context

        Returns:
            Fully rendered prompt text
        """
        # Load shared blocks
        full_context = {**context, **metadata}
        full_context["autonomy_block"] = self._load_block("autonomy.md")
        full_context["sprint_planning_block"] = self._load_block("sprint_planning.md")

        # Render standard blocks
        from jules.scheduler import (
            IDENTITY_BRANDING,
            JOURNAL_MANAGEMENT,
            CELEBRATION,
            PRE_COMMIT_INSTRUCTIONS,
            sprint_manager,
        )

        full_context["identity_branding"] = self.jinja_env.from_string(IDENTITY_BRANDING).render(
            **full_context
        )
        full_context["journal_management"] = self.jinja_env.from_string(JOURNAL_MANAGEMENT).render(
            **full_context
        )
        full_context["empty_queue_celebration"] = self.jinja_env.from_string(CELEBRATION).render(
            **full_context
        )
        full_context["pre_commit_instructions"] = self.jinja_env.from_string(
            PRE_COMMIT_INSTRUCTIONS
        ).render(**full_context)

        # Add sprint context
        sprint_context = sprint_manager.get_sprint_context(metadata.get("id", "unknown"))
        body_with_sprint = body_template + sprint_context

        # Render final body
        return self.jinja_env.from_string(body_with_sprint).render(**full_context).strip()

    def _load_block(self, block_name: str) -> str:
        """Load a shared prompt block from .jules/blocks/.

        Args:
            block_name: Block filename (e.g., "autonomy.md")

        Returns:
            Block content or empty string if not found
        """
        blocks_dir = self.personas_dir.parent / "blocks"
        block_path = blocks_dir / block_name
        if not block_path.exists():
            return ""
        try:
            return block_path.read_text().strip()
        except OSError:
            return ""

    def _ensure_journals_directory(self, persona_dir: Path) -> None:
        """Ensure journals/ subdirectory exists for a persona.

        Args:
            persona_dir: Path to persona directory
        """
        journals_dir = persona_dir / "journals"
        journals_dir.mkdir(parents=True, exist_ok=True)

    def _collect_journals(self, persona_dir: Path) -> str:
        """Collect recent journal entries for a persona.

        Args:
            persona_dir: Path to persona directory

        Returns:
            Formatted string with up to 10 most recent journal entries
        """
        journals_dir = persona_dir / "journals"
        if not journals_dir.exists():
            return ""

        # Get sorted journal files (most recent last)
        journal_files = sorted(journals_dir.glob("*.md"))

        # Keep only last 10 entries
        if len(journal_files) > 10:
            journal_files = journal_files[-10:]

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
                    entries.append(f"\n--- Journal Entry: {journal_file.name} ---\n{content}\n")
            except Exception:
                pass  # Skip malformed journals

        return "\n".join(entries)
