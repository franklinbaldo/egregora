#!/usr/bin/env python3
"""Generate project documentation from templates.

This script generates consistent documentation files from Jinja2 templates,
ensuring that agent-specific guides (CLAUDE.md, AGENTS.md, GEMINI.md) remain
synchronized and don't drift apart.

Usage:
    python scripts/generate_docs.py

This will regenerate all templated documentation files.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def generate_agent_guides() -> None:
    """Generate agent-specific guide files from template."""
    # Setup paths
    repo_root = Path(__file__).parent.parent
    templates_dir = repo_root / "scripts" / "templates"

    # Setup Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(),
    )

    # Load template
    template = env.get_template("AGENT_GUIDE.md.jinja2")

    # Agent configurations
    agents = [
        {
            "filename": "CLAUDE.md",
            "agent_name": "CLAUDE",
            "agent_display_name": "Claude Code",
        },
        {
            "filename": "AGENTS.md",
            "agent_name": "AGENTS",
            "agent_display_name": "the Agent",
        },
        {
            "filename": "GEMINI.md",
            "agent_name": "GEMINI",
            "agent_display_name": "Gemini",
        },
    ]

    # Generate each agent guide
    for agent_config in agents:
        output_path = repo_root / agent_config["filename"]
        content = template.render(**agent_config)
        output_path.write_text(content, encoding="utf-8")
        print(f"✓ Generated {agent_config['filename']}")


def main() -> None:
    """Generate all templated documentation."""
    print("Generating documentation from templates...")
    print()

    generate_agent_guides()

    print()
    print("Documentation generation complete!")
    print()
    print("⚠️  These files are auto-generated. Do not edit them directly!")
    print("   Instead, edit the templates in scripts/templates/")


if __name__ == "__main__":
    main()
