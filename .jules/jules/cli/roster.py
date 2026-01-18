"""
Roster: Discover your fellow personas.

Provides:
- roster list: See all personas in the team
- roster view: Get details about a specific persona (fully rendered)
"""
from pathlib import Path
import typer
import frontmatter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from jules.scheduler.loader import PersonaLoader

app = typer.Typer(
    name="roster",
    help="👥 Discover your fellow personas: list all or view details",
    no_args_is_help=True,
)

console = Console()


def get_personas_dir() -> Path:
    """Find the personas directory."""
    candidates = [
        Path(".jules/personas"),
        Path("personas"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find personas directory")


@app.command(name="list")
def list_personas():
    """
    👥 List all personas in the team.

    Shows each persona's ID, emoji, and description in a rich table.

    Example:
        my-tools roster list
    """
    try:
        personas_dir = get_personas_dir()
        personas = []

        for prompt_file in sorted(personas_dir.glob("*/prompt.md.j2")):
            try:
                post = frontmatter.load(prompt_file)
                persona_id = post.metadata.get("id", prompt_file.parent.name)
                emoji = post.metadata.get("emoji", "🤖")
                description = post.metadata.get("description", "").strip()

                # Cleanup: remove surrounding quotes if they exist (sometimes YAML adds them)
                if (description.startswith('"') and description.endswith('"')) or \
                   (description.startswith("'") and description.endswith("'")):
                    description = description[1:-1].strip()

                # Normalize whitespace
                description = " ".join(description.split())

                personas.append((persona_id, emoji, description))
            except Exception:
                continue

        if not personas:
            console.print("[red]No personas found.[/red]")
            raise typer.Exit(code=1)

        # Create rich table
        table = Table(
            title="👥 Team Roster",
            show_header=True,
            header_style="bold cyan",
            box=None,
            padding=(0, 1)
        )
        table.add_column("", style="", width=3)  # Emoji
        table.add_column("Persona", style="bold cyan", width=15)
        table.add_column("Description", style="white")

        for pid, emoji, desc in personas:
            table.add_row(emoji, pid, desc)

        console.print(table)
        console.print(f"\n[dim]Total: {len(personas)} personas[/dim]")
        console.print("[dim]Use 'my-tools roster view <persona_id>' for full details[/dim]")

    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(code=1)


@app.command(name="view")
def view_persona(
    persona_id: str = typer.Argument(..., help="The persona ID to view (e.g., refactor, curator)")
):
    """
    🔍 View the fully rendered prompt for a specific persona.

    This shows exactly what the persona sees when starting a session.

    Example:
        my-tools roster view refactor
    """
    try:
        personas_dir = get_personas_dir()
        prompt_file = personas_dir / persona_id / "prompt.md.j2"

        if not prompt_file.exists():
            console.print(f"[red]❌ Persona '{persona_id}' not found[/red]")
            console.print("[dim]Try: my-tools roster list[/dim]")
            raise typer.Exit(code=1)

        base_context = {
            "repo_owner": "team",
            "repo_name": "repo",
            "open_prs": [],
        }

        loader = PersonaLoader(personas_dir, base_context)
        config = loader.load_persona(prompt_file)

        # Print with Rich
        console.print(Panel(
            f"[bold]{config.emoji} {config.id.upper()}[/bold]\n[dim]{config.description}[/dim]",
            title="Persona Details",
            border_style="cyan"
        ))

        console.print("\n[bold cyan]Full Rendered Prompt:[/bold cyan]\n")
        console.print(Markdown(config.prompt_body))

    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]❌ Error rendering persona: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
