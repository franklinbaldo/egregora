"""
MY-TOOLS: Your Personal Toolkit for the Jules Environment

Bundles all persona utilities:
- login/journal/loop-break for session management
- email for inter-persona communication
- roster for discovering fellow personas
"""
import typer
from typing import List, Optional
from repo.features.session import SessionManager
from repo.features.hire import HireManager
from repo.cli.mail import app as mail_app
from repo.cli.roster import app as roster_app
from repo.cli.skills import app as skills_app
from repo.cli.persona import app as persona_app
from repo.features.pulse import PulseManager
from repo.features.logging import log_tool_command

HELP_TEXT = """
[bold cyan]JULES PROJECT: SYSTEM TOOLKIT[/bold cyan]
[dim]"Coordinating the future of autonomous software engineering."[/dim]

[bold yellow]── SESSION MANAGEMENT ──[/bold yellow]
  [bold blue]login[/bold blue]        Initialize your persona session.
  [bold blue]journal[/bold blue]      Document work progress and session goals.
  [bold blue]loop-break[/bold blue]   Emergency interrupt for recursive feedback.

[bold yellow]── TEAM & COMMUNICATION ──[/bold yellow]
  [bold magenta]email[/bold magenta]        Inter-persona messaging system.
  [bold magenta]roster[/bold magenta]       Discover and view team members.
  [bold magenta]skills[/bold magenta]       Discover specialized instruction sets.
  [bold magenta]persona[/bold magenta]      Manage and inspect personas.
  [bold magenta]hire[/bold magenta]         Provision new persona identities.

[bold yellow]── WORKFLOW ──[/bold yellow]
  1. [dim]my-tools login[/dim]        [dim]Authenticate and set goals.[/dim]
  2. [dim]my-tools email inbox[/dim] [dim]Check for pending coordination.[/dim]
  3. [dim]my-tools journal[/dim]     [dim]Finalize outputs before logout.[/dim]

[bold yellow]── UTILITIES ──[/bold yellow]
  --help        Show this documentation.
"""

app = typer.Typer(
    help=HELP_TEXT,
    rich_markup_mode="rich"
)
app.add_typer(mail_app, name="email")
app.add_typer(roster_app, name="roster")
app.add_typer(skills_app, name="skills")
app.add_typer(persona_app, name="persona")

session_manager = SessionManager()
hire_manager = HireManager()
pulse_manager = PulseManager()

@app.command()
@log_tool_command(require_login=False)
def login(
    user: str = typer.Option(..., "--user", "-u", help="Your persona ID (e.g. curator@team)"),
    password: str = typer.Option(..., "--password", "-p", help="Your identity token (Access Key)"),
    goals: List[str] = typer.Option(None, "--goal", "--goals", "-g", help="Session objectives")
):
    """
    🔐 AUTHENTICATE SESSION.
    Initialize your work environment and set goals.
    """
    try:
        session_manager.login(user, password, goals or [])
        print(f"✅ Logged in as {user}")
        print(f"🎯 Goals set: {', '.join(goals) if goals else '(none)'}")
        print("📋 Session configuration created.")

        # Display Sitrep
        from rich import print as rprint
        sequence = session_manager.get_active_sequence()
        sitrep = pulse_manager.get_sitrep(user, sequence)
        rprint("\n" + pulse_manager.format_sitrep(sitrep) + "\n")
    except ValueError as e:
        print(f"❌ Login failed: {e}")
        raise typer.Exit(code=1)

@app.command()
@log_tool_command()
def journal(
    content: str = typer.Option(..., "--content", "-c", help="Detailed work report"),
    password: str = typer.Option(..., "--password", "-p", help="Identity verification")
):
    """
    📝 DOCUMENT PROGRESS.
    Record your achievements for the active session.
    """
    try:
        path = session_manager.create_journal_entry(content, password)
        print(f"📜 Journal entry created: {path}")
    except (RuntimeError, ValueError) as e:
        print(f"⚠️ Error: {e}")
        raise typer.Exit(code=1)

@app.command(name="loop-break")
@log_tool_command()
def loop_break(
    reason: str = typer.Option(..., "--reason", "-r", help="Reason for the manual interrupt")
):
    """
    🛑 EMERGENCY INTERRUPT.
    Use only when stuck in a recursive feedback loop.
    """
    try:
        session_manager.loop_break(reason)
        print("🛑 Session interrupted. Cleanup protocol engaged.")
    except RuntimeError as e:
        print(f"⚠️ Error: {e}")
        raise typer.Exit(code=1)

@app.command()
@log_tool_command()
def hire(
    id: str = typer.Option(..., "--id", help="The unique ID for the new persona"),
    emoji: str = typer.Option(..., "--emoji", help="Persona icon/emoji"),
    description: str = typer.Option(..., "--description", help="Persona description"),
    role: str = typer.Option(..., "--role", help="Specific persona role/expertise"),
    goal: str = typer.Option(..., "--goal", help="Persona's primary goal"),
    context: str = typer.Option("TBD", "--context", help="Initial context for the persona"),
    constraints: str = typer.Option("- Follow project conventions", "--constraints", help="Persona constraints"),
    guardrails: str = typer.Option("✅ Always follow BDD principles", "--guardrails", help="Persona guardrails"),
    verification: str = typer.Option("uv run pytest", "--verification", help="Verification command"),
    workflow: str = typer.Option("1. 🔍 OBSERVE\n2. 🎯 SELECT\n3. 🛠️ IMPLEMENT\n4. ✅ VERIFY", "--workflow", help="Persona workflow"),
    password: str = typer.Option(..., "--password", help="Identity verification")
):
    """
    🤝 PROVISION NEW PERSONA.
    Expand the team by creating a new specialized persona identity.
    """
    try:
        voter_id = session_manager.get_active_persona()
        if not voter_id:
            print("❌ No active session. Please login first.")
            raise typer.Exit(code=1)

        if not session_manager.validate_password(voter_id, password):
            print("❌ Auth failed: Invalid password.")
            raise typer.Exit(code=1)

        path = hire_manager.hire_persona(
            persona_id=id,
            emoji=emoji,
            description=description,
            hired_by=voter_id,
            role=role,
            goal=goal,
            context=context,
            constraints=constraints,
            guardrails=guardrails,
            verification=verification,
            workflow=workflow
        )
        print(f"✅ Persona '{id}' successfully hired! Prompt created at {path}")

    except Exception as e:
        print(f"❌ Hire failed: {e}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
