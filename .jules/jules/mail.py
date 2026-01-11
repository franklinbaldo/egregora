"""Mail system for persona coordination using Maildir format.

This module provides async messaging between personas using the standard
Maildir format (RFC 3501) and Python email library (RFC 822).

Architecture:
- Each persona has a mailbox: .jules/mail/{persona_id}/
- Maildir structure: new/ (unread), cur/ (read), tmp/ (temp)
- Messages use RFC 822 format (standard email)
- Supports attachments (e.g., .patch files)

Example:
    >>> from jules.mail import send_message, get_inbox
    >>> send_message(
    ...     from_persona="weaver",
    ...     to_persona="curator",
    ...     subject="Conflict in PR #123",
    ...     body="Your PR conflicts with refactor's changes..."
    ... )
    >>> inbox = get_inbox("curator", unread_only=True)
    >>> print(f"You have {len(inbox)} unread messages")
"""

from __future__ import annotations

import email
import mailbox
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any

__all__ = [
    "send_message",
    "get_inbox",
    "get_message",
    "mark_read",
    "get_mail_root",
]

# Mail storage root
DEFAULT_MAIL_ROOT = Path(".jules/mail")


def get_mail_root() -> Path:
    """Get the mail storage root directory."""
    return DEFAULT_MAIL_ROOT


def _ensure_mailbox(persona_id: str) -> mailbox.Maildir:
    """Ensure persona mailbox exists and return Maildir object."""
    mailbox_path = get_mail_root() / persona_id
    mailbox_path.mkdir(parents=True, exist_ok=True)

    # Create Maildir subdirectories (new, cur, tmp)
    for subdir in ["new", "cur", "tmp"]:
        (mailbox_path / subdir).mkdir(exist_ok=True)

    return mailbox.Maildir(str(mailbox_path), factory=None, create=True)


def send_message(
    from_persona: str,
    to_persona: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> str:
    """Send a message from one persona to another.

    Args:
        from_persona: Sender persona ID (e.g., "weaver")
        to_persona: Recipient persona ID (e.g., "curator")
        subject: Message subject
        body: Message body (plain text)
        attachments: Optional list of (filename, content) tuples

    Returns:
        Message ID (unique identifier)

    Example:
        >>> msg_id = send_message(
        ...     "weaver", "curator",
        ...     "Conflict in PR #123",
        ...     "Your PR conflicts with...",
        ...     attachments=[("pr-123.patch", patch_bytes)]
        ... )
    """
    # Create multipart message
    msg = MIMEMultipart()
    msg["From"] = f"{from_persona}@jules.local"
    msg["To"] = f"{to_persona}@jules.local"
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="jules.local")

    # Add body
    msg.attach(MIMEText(body, "plain"))

    # Add attachments if provided
    if attachments:
        from email.mime.application import MIMEApplication

        for filename, content in attachments:
            attachment = MIMEApplication(content)
            attachment.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(attachment)

    # Get recipient mailbox and add message
    mbox = _ensure_mailbox(to_persona)
    mbox.add(msg)
    mbox.close()

    return msg["Message-ID"]


def get_inbox(persona_id: str, unread_only: bool = False) -> list[dict[str, Any]]:
    """Get messages from persona's inbox.

    Args:
        persona_id: Persona ID
        unread_only: If True, return only unread messages (in 'new' folder)

    Returns:
        List of message dictionaries with keys:
        - id: Message key (for mark_read)
        - from: Sender persona
        - subject: Subject line
        - date: Date string
        - body: Message body preview (first 500 chars)
        - is_read: Whether message has been read

    Example:
        >>> inbox = get_inbox("curator", unread_only=True)
        >>> for msg in inbox:
        ...     print(f"{msg['from']}: {msg['subject']}")
    """
    mbox = _ensure_mailbox(persona_id)
    messages = []

    mailbox_path = get_mail_root() / persona_id

    for key in mbox.keys():
        msg = mbox[key]

        # Check if message is in 'new' (unread) or 'cur' (read) directory
        # Maildir keys are like "1234567890.M0P12345.hostname"
        is_read = (mailbox_path / "cur" / key).exists()

        # Skip read messages if unread_only
        if unread_only and is_read:
            continue

        # Extract sender (strip @jules.local domain)
        from_addr = msg.get("From", "unknown")
        from_persona = from_addr.split("@")[0] if "@" in from_addr else from_addr

        # Get body (first text/plain part)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

        messages.append(
            {
                "id": key,
                "from": from_persona,
                "subject": msg.get("Subject", "(no subject)"),
                "date": msg.get("Date", ""),
                "body": body[:500] + ("..." if len(body) > 500 else ""),
                "is_read": is_read,
            }
        )

    mbox.close()
    return messages


def get_message(persona_id: str, message_id: str) -> dict[str, Any] | None:
    """Get full message details including attachments.

    Args:
        persona_id: Persona ID
        message_id: Message key from get_inbox()

    Returns:
        Dictionary with:
        - from: Sender
        - subject: Subject
        - date: Date
        - body: Full body
        - attachments: List of (filename, bytes) tuples
        Or None if message not found

    Example:
        >>> msg = get_message("curator", "1234567890.123.mbox")
        >>> print(msg["body"])
        >>> for filename, content in msg["attachments"]:
        ...     print(f"Attachment: {filename}")
    """
    mbox = _ensure_mailbox(persona_id)

    try:
        msg = mbox[message_id]
    except KeyError:
        mbox.close()
        return None

    # Extract sender
    from_addr = msg.get("From", "unknown")
    from_persona = from_addr.split("@")[0] if "@" in from_addr else from_addr

    # Get body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

    # Get attachments
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                filename = part.get_filename() or "unnamed"
                content = part.get_payload(decode=True)
                attachments.append((filename, content))

    mbox.close()

    return {
        "from": from_persona,
        "subject": msg.get("Subject", "(no subject)"),
        "date": msg.get("Date", ""),
        "body": body,
        "attachments": attachments,
    }


def mark_read(persona_id: str, message_id: str) -> bool:
    """Mark a message as read (move from new/ to cur/).

    Args:
        persona_id: Persona ID
        message_id: Message key

    Returns:
        True if successful, False if message not found

    Example:
        >>> mark_read("curator", "1234567890.123.mbox")
    """
    import os
    import shutil

    mailbox_path = get_mail_root() / persona_id
    new_file = mailbox_path / "new" / message_id
    cur_file = mailbox_path / "cur" / message_id

    # Move from new/ to cur/ if exists in new/
    if new_file.exists():
        shutil.move(str(new_file), str(cur_file))
        return True

    # Already in cur/ or doesn't exist
    return cur_file.exists()
