"""CLI tool for Jules mail system.

Usage:
    python -m jules.mail_cli send --to curator --subject "..." --body "..."
    python -m jules.mail_cli inbox --persona curator
    python -m jules.mail_cli read <msg_id> --persona curator
    python -m jules.mail_cli mark-read <msg_id> --persona curator

Or via direct execution:
    ./mail_cli.py inbox --persona curator
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

# Add jules module to path
sys.path.insert(0, str(Path(__file__).parent))

from mail import get_inbox, get_message, mark_read, send_message

app = typer.Typer(help="Jules Mail CLI - Inter-persona messaging system")
console = Console()


@app.command()
def send(
    to: str = typer.Option(..., "--to", "-t", help="Recipient persona ID"),
    subject: str = typer.Option(..., "--subject", "-s", help="Message subject"),
    body: str = typer.Option(..., "--body", "-b", help="Message body"),
    from_persona: str = typer.Option("unknown", "--from", "-f", help="Sender persona ID"),
    attach: Optional[list[str]] = typer.Option(None, "--attach", "-a", help="Attachment file paths"),
) -> None:
    """Send a message to another persona.

    Example:
        jules-mail send --to curator --from weaver \\
            --subject "Conflict in PR #123" \\
            --body "Your PR conflicts with refactor's changes"
    """
    attachments = []
    if attach:
        for file_path in attach:
            path = Path(file_path)
            if not path.exists():
                console.print(f"[red]❌ Attachment not found: {file_path}[/red]")
                raise typer.Exit(1)
            content = path.read_bytes()
            attachments.append((path.name, content))

    try:
        msg_id = send_message(
            from_persona=from_persona,
            to_persona=to,
            subject=subject,
            body=body,
            attachments=attachments if attachments else None,
        )
        console.print(f"[green]✅ Message sent to {to}[/green]")
        console.print(f"Message-ID: {msg_id}")
    except Exception as e:
        console.print(f"[red]❌ Failed to send message: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def inbox(
    persona: str = typer.Option(..., "--persona", "-p", help="Persona ID"),
    unread: bool = typer.Option(False, "--unread", "-u", help="Show only unread messages"),
) -> None:
    """List messages in persona's inbox.

    Example:
        jules-mail inbox --persona curator --unread
    """
    try:
        messages = get_inbox(persona, unread_only=unread)

        if not messages:
            status = "unread" if unread else "total"
            console.print(f"[yellow]📭 No {status} messages for {persona}[/yellow]")
            return

        # Create table
        table = Table(title=f"📬 {persona}'s Inbox ({len(messages)} messages)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("From", style="green")
        table.add_column("Subject", style="white")
        table.add_column("Date", style="blue")
        table.add_column("Status", style="yellow")

        for msg in messages:
            # Truncate ID for display
            msg_id_short = msg["id"][:20] + "..." if len(msg["id"]) > 20 else msg["id"]
            status = "📖 Read" if msg["is_read"] else "✉️  New"

            table.add_row(
                msg_id_short,
                msg["from"],
                msg["subject"],
                msg["date"][:20],  # Truncate date
                status,
            )

        console.print(table)
        console.print(f"\n💡 Read a message: [cyan]jules-mail read <msg_id> --persona {persona}[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Failed to read inbox: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def read(
    message_id: str = typer.Argument(..., help="Message ID from inbox"),
    persona: str = typer.Option(..., "--persona", "-p", help="Persona ID"),
    auto_mark_read: bool = typer.Option(True, "--mark-read/--no-mark-read", help="Auto mark as read"),
) -> None:
    """Read a message and display full content.

    Example:
        jules-mail read 1234567890.123.mbox --persona curator
    """
    try:
        msg = get_message(persona, message_id)

        if not msg:
            console.print(f"[red]❌ Message not found: {message_id}[/red]")
            raise typer.Exit(1)

        # Display message
        console.print(f"\n[bold cyan]From:[/bold cyan] {msg['from']}")
        console.print(f"[bold cyan]Subject:[/bold cyan] {msg['subject']}")
        console.print(f"[bold cyan]Date:[/bold cyan] {msg['date']}")
        console.print(f"\n[bold white]Message:[/bold white]")
        console.print(f"{msg['body']}\n")

        # Display attachments
        if msg["attachments"]:
            console.print(f"[bold yellow]📎 Attachments ({len(msg['attachments'])}):[/bold yellow]")
            for filename, content in msg["attachments"]:
                size_kb = len(content) / 1024
                console.print(f"  - {filename} ({size_kb:.1f} KB)")

        # Auto mark as read
        if auto_mark_read:
            mark_read(persona, message_id)
            console.print(f"\n[green]✅ Message marked as read[/green]")

    except Exception as e:
        console.print(f"[red]❌ Failed to read message: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def mark_as_read(
    message_id: str = typer.Argument(..., help="Message ID from inbox"),
    persona: str = typer.Option(..., "--persona", "-p", help="Persona ID"),
) -> None:
    """Mark a message as read.

    Example:
        jules-mail mark-read 1234567890.123.mbox --persona curator
    """
    try:
        success = mark_read(persona, message_id)
        if success:
            console.print(f"[green]✅ Message marked as read[/green]")
        else:
            console.print(f"[red]❌ Message not found: {message_id}[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Failed to mark message: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
