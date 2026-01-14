import typer
from typing import List, Optional
import os
from jules.features.mail import send_message, list_inbox, get_message, mark_read

app = typer.Typer(
    help="""
    JULES MAIL CLI: A hybrid S3/Local communication system for AI Personas.
    
    This tool allows personas (AI agents) to send and receive internal 'mail' messages.
    It supports both offline local storage (Maildir) and cloud-scale S3 buckets (Internet Archive).
    
    CONFIGURATION:
    Configuration is primarily handled via environment variables:
    - JULES_PERSONA: Your current identity (e.g., 'weaver@team', 'curator@team').
    - JULES_MAIL_STORAGE: 's3' or 'local' (default).
    - JULES_MAIL_BUCKET: The S3 bucket name/IA item (e.g., 'jules-mail-frank-2026').
    
    QUICK START & EXAMPLES:
    
    1. Send a message with all parameters:
       jules-mail send --to curator@team --subject "Urgent: Data Sync" --body "Check the latest logs." --from weaver@team --attach "logs.txt" --attach "report.pdf"
    
    2. Check your inbox (unread only):
       jules-mail inbox --persona weaver@team --unread
    
    3. Read a specific message and mark as read:
       jules-mail read "be242fd7-0373-4530-aba2-e4d3f044290b" --persona weaver@team
    
    4. Switch to S3 for a single command:
       JULES_MAIL_STORAGE=s3 jules-mail inbox
    """
)

@app.command()
def send(
    to: str = typer.Option(
        ..., "--to", 
        help="Recipient Persona ID. This corresponds to the target folder or S3 prefix."
    ),
    subject: str = typer.Option(
        ..., "--subject", 
        help="A brief descriptive title for the message."
    ),
    body: str = typer.Option(
        ..., "--body", 
        help="The full content of the message. Use standard text formatting."
    ),
    from_persona: str = typer.Option(
        None, "--from", "-f", 
        help="Your Persona ID. If not provided, the JULES_PERSONA environment variable MUST be set.",
        envvar="JULES_PERSONA"
    ),
    attach: Optional[List[str]] = typer.Option(
        None, "--attach", 
        help="Optional: List of file names or identifiers to associate with this message."
    ),
):
    """
    Send a digital message to another persona.
    
    The message will be persisted to the configured backend (S3 or Local).
    If using S3, it will be stored as an .eml file in the recipient's prefix.
    
    Example:
        jules-mail send --to curator@team --subject "Data Update" --body "The latest sync is complete."
    """
    if not from_persona:
        print("Error: --from or JULES_PERSONA env var required.")
        raise typer.Exit(code=1)
        
    try:
        key = send_message(from_persona, to, subject, body, attach)
        print(f"✅ Sent message to {to} (Key: {key})")
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        raise typer.Exit(code=1)

@app.command()
def inbox(
    persona: str = typer.Option(
        None, "--persona", "-p", 
        help="Which persona's inbox to check. Defaults to JULES_PERSONA.",
        envvar="JULES_PERSONA"
    ),
    unread: bool = typer.Option(
        False, "--unread", 
        help="Filter results to show only messages that haven't been 'read' yet."
    ),
):
    """
    List messages in your persona's inbox.
    
    Returns a list of messages with their unique Keys, Senders, and Subjects.
    New/Unread messages are marked with [NEW].
    
    Example:
        jules-mail inbox --persona weaver@team --unread
    """
    if not persona:
        print("Error: --persona or JULES_PERSONA env var required.")
        raise typer.Exit(code=1)
        
    try:
        messages = list_inbox(persona, unread_only=unread)
        if not messages:
            print(f"📬 Inbox for {persona} is empty.")
            return

        print(f"📬 Inbox for {persona}:")
        for msg in messages:
            status = "[NEW]" if not msg["read"] else "[   ]"
            print(f"{status} {msg['key']} | From: {msg['from']} | Subject: {msg['subject']}")
    except Exception as e:
        print(f"❌ Error reading inbox: {e}")
        raise typer.Exit(code=1)

@app.command()
def read(
    key: str = typer.Argument(
        ..., 
        help="The unique Key/ID of the message to retrieve. Get this from the 'inbox' command."
    ),
    persona: str = typer.Option(
        None, "--persona", "-p", 
        help="Your Persona ID. Defaults to JULES_PERSONA.",
        envvar="JULES_PERSONA"
    ),
):
    """
    Open and display the full content of a specific message.
    
    IMPORTANT: Reading a message automatically marks it as 'Read' in the system.
    
    Example:
        jules-mail read be242fd7-0373-4530-aba2-e4d3f044290b --persona weaver@team
    """
    if not persona:
        print("Error: --persona or JULES_PERSONA env var required.")
        raise typer.Exit(code=1)
        
    try:
        msg = get_message(persona, key)
        print(f"--- Message: {key} ---")
        print(f"From:    {msg['from']}")
        print(f"To:      {msg['to']}")
        print(f"Subject: {msg['subject']}")
        print(f"Date:    {msg['date']}")
        print("-" * 20)
        print(msg["body"])
        print("-" * 20)
        
        # Auto mark as read
        mark_read(persona, key)
        print(f"✅ Marked as read.")
    except Exception as e:
        print(f"❌ Error reading message: {e}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
