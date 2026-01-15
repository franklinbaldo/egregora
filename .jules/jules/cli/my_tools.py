"""
MY-TOOLS: Your Personal Toolkit for the Jules Environment

Bundles all persona utilities:
- login/journal/loop-break for session management
- email for inter-persona communication
"""
import typer
from typing import List, Optional
from jules.features.session import SessionManager
from jules.cli.mail import app as mail_app

HELP_TEXT = """
╔══════════════════════════════════════════════════════════════════╗
║                    MY-TOOLS: Personal Toolkit                    ║
╠══════════════════════════════════════════════════════════════════╣
║  Your interface for session management and team communication.   ║
║                                                                  ║
║  🔐 SESSION MANAGEMENT                                           ║
║    login       Start your work shift (required first)            ║
║    journal     Document your work before finishing               ║
║    loop-break  Emergency stop if stuck in a loop                 ║
║                                                                  ║
║  📧 COMMUNICATION                                                ║
║    email send    Send a message to another persona               ║
║    email inbox   Check your inbox for messages                   ║
║    email read    Read a specific message by key                  ║
║                                                                  ║
║  QUICK START:                                                    ║
║    1. my-tools login -u curator -p <token> -g "Fix CI"           ║
║    2. my-tools email inbox -p curator                            ║
║    3. <do your work>                                             ║
║    4. my-tools email send --to weaver --subject "Done"           ║
║    5. my-tools journal -c "Fixed CI issue" -p <token>            ║
║                                                                  ║
║  For subcommand help: my-tools <command> --help                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

app = typer.Typer(
    name="my-tools",
    help=HELP_TEXT,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Add mail CLI as a subcommand group "email"
app.add_typer(
    mail_app, 
    name="email", 
    help="📧 Email communication tools: send, inbox, read messages"
)

session_manager = SessionManager()

@app.command()
def login(
    user: str = typer.Option(..., "--user", "-u", help="Your persona ID (e.g. curator@team)"),
    password: str = typer.Option(..., "--password", "-p", help="Your unique identity token (UUIDv5 of your persona ID)"),
    goals: List[str] = typer.Option([], "--goals", "-g", help="Goals for this session. Can be specified multiple times.")
):
    """
    🔐 Clock in for work.
    
    This MUST be your first action when starting a session.
    It configures your environment, sets your goals, and enables journaling.
    
    Example:
        my-tools login --user weaver@team --password abc123-... --goals "Fix CI" --goals "Update docs"
    """
    try:
        session_manager.login(user, password, goals)
        print(f"✅ Logged in as {user}")
        print(f"🎯 Goals set: {', '.join(goals) if goals else '(none)'}")
        print("📋 Session configuration created.")
    except ValueError as e:
        print(f"❌ Login failed: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

@app.command()
def journal(
    content: str = typer.Option(..., "--content", "-c", help="Detailed description of work done and goals achieved"),
    password: str = typer.Option(..., "--password", "-p", help="Identity verification (same as login)")
):
    """
    📝 File a journal entry.
    
    You MUST call this before finishing your shift (before commits or stopping).
    It documents your work execution against your session goals.
    
    Example:
        my-tools journal --content "Fixed CI by updating Python version. Docs updated for new API." --password abc123-...
    """
    try:
        path = session_manager.create_journal_entry(content, password)
        print(f"✅ Journal entry saved to {path}")
    except ValueError as e:
        print(f"❌ Auth failed: {e}")
        raise typer.Exit(code=1)
    except RuntimeError as e:
        print(f"❌ Session error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

@app.command(name="loop-break")
def loop_break(
    reason: str = typer.Option(..., "--reason", "-r", help="Why are you stopping? Be descriptive.")
):
    """
    🛑 EMERGENCY STOP.
    
    Use this if you are stuck in a loop or cannot proceed.
    Captures current context and signals end of session.
    
    Example:
        my-tools loop-break --reason "Infinite loop in CI retry logic"
    """
    try:
        session_manager.loop_break(reason)
        print("🛑 Session STOPPED. Context captured in loop_break_context.json.")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
