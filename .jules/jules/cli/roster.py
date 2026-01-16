"""
Roster: Discover your fellow personas.

Provides:
- roster list: See all personas in the team
- roster view: Get details about a specific persona (fully rendered)
"""
from pathlib import Path
import typer
import frontmatter

app = typer.Typer(
    name="roster",
    help="👥 Discover your fellow personas: list all or view details",
    no_args_is_help=True,
)


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
    
    Shows each persona's ID, emoji, and description.
    
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
                description = post.metadata.get("description", "")
                # Truncate description for display
                if len(description) > 50:
                    description = description[:47] + "..."
                personas.append((persona_id, emoji, description))
            except Exception:
                continue
        
        if not personas:
            print("No personas found.")
            raise typer.Exit(code=1)
        
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║                         TEAM ROSTER                              ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
        for pid, emoji, desc in personas:
            print(f"║  {emoji} {pid:<15} {desc:<45}║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(f"\nTotal: {len(personas)} personas")
        print("Use 'my-tools roster view <persona_id>' for details")
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
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
            print(f"❌ Persona '{persona_id}' not found")
            print(f"   Try: my-tools roster list")
            raise typer.Exit(code=1)
        
        # Use PersonaLoader to render the full prompt
        from jules.scheduler.loader import PersonaLoader
        
        base_context = {
            "repo_owner": "team",
            "repo_name": "repo",
            "open_prs": [],
        }
        
        loader = PersonaLoader(personas_dir, base_context)
        config = loader.load_persona(prompt_file)
        
        # Print header
        print(f"\n{'='*70}")
        print(f"PERSONA: {config.emoji} {config.id}")
        print(f"{'='*70}\n")
        
        # Print the rendered prompt
        print(config.prompt_body)
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        print(f"❌ Error rendering persona: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
