"""Command processing for /egregora system commands.

Handles detection, parsing, filtering, and conversion of user commands
into system ANNOUNCEMENT documents.
"""

import re
from datetime import datetime
from typing import Any

from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import Document, DocumentType


def is_command(text: str) -> bool:
    """Check if message text is an /egregora command.
    
    Args:
        text: Message text to check
        
    Returns:
        True if text starts with /egregora (case-insensitive)
    """
    return text.strip().lower().startswith("/egregora")


def parse_command(text: str) -> dict[str, Any]:
    """Parse /egregora command into structured data.
    
    Args:
        text: Command text (e.g., "/egregora avatar set https://...")
        
    Returns:
        Dict with 'type', 'action', and 'params'
        
    Examples:
        >>> parse_command("/egregora avatar set https://example.com/img.jpg")
        {'type': 'avatar', 'action': 'set', 'params': {'url': 'https://...'}}
        
        >>> parse_command("/egregora bio I am a researcher")
        {'type': 'bio', 'action': 'update', 'params': {'bio': 'I am a researcher'}}
    """
    # Remove /egregora prefix (case-insensitive)
    text = re.sub(r"^/egregora\s+", "", text.strip(), flags=re.IGNORECASE)
    
    # Parse command type and parameters
    parts = text.split(None, 1)
    
    if not parts:
        return {"type": "unknown", "action": "unknown", "params": {}}
    
    cmd_type = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""
    
    if cmd_type == "avatar":
        # /egregora avatar set URL
        action_parts = rest.split(None, 1)
        action = action_parts[0] if action_parts else "set"
        url = action_parts[1] if len(action_parts) > 1 else ""
        return {
            "type": "avatar",
            "action": action,
            "params": {"url": url}
        }
    
    elif cmd_type == "bio":
        # /egregora bio TEXT
        return {
            "type": "bio",
            "action": "update",
            "params": {"bio": rest}
        }
    
    elif cmd_type == "interests":
        # /egregora interests COMMA,SEPARATED,LIST
        return {
            "type": "interests",
            "action": "update",
            "params": {"interests": rest}
        }
    
    else:
        return {
            "type": cmd_type,
            "action": "unknown",
            "params": {"raw": rest}
        }


def filter_commands(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter out command messages from message list.
    
    Used to remove commands before sending messages to LLM.
    
    Args:
        messages: List of message dicts with 'text' field
        
    Returns:
        List of messages without commands
    """
    return [msg for msg in messages if not is_command(msg.get("text", ""))]


def extract_commands(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract only command messages from message list.
    
    Args:
        messages: List of message dicts with 'text' field
        
    Returns:
        List of only command messages
    """
    return [msg for msg in messages if is_command(msg.get("text", ""))]


def command_to_announcement(message: dict[str, Any]) -> Document:
    """Convert command message to ANNOUNCEMENT document.
    
    Args:
        message: Command message dict with:
            - text: Command text
            - author_uuid: UUID of command issuer
            - author_name: Name of command issuer
            - timestamp: ISO timestamp
            
    Returns:
        ANNOUNCEMENT Document
    """
    text = message["text"]
    author_uuid = message["author_uuid"]
    author_name = message["author_name"]
    timestamp = message["timestamp"]
    
    # Parse command
    cmd = parse_command(text)
    cmd_type = cmd["type"]
    params = cmd["params"]
    
    # Extract date from timestamp
    if isinstance(timestamp, str):
        try:
            date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
        except (ValueError, AttributeError):
            date = timestamp.split("T")[0]  # Fallback to date part
    else:
        date = datetime.now().date().isoformat()
    
    # Generate content based on command type
    if cmd_type == "avatar":
        title = f"{author_name} Updated Avatar"
        content = f"""# {title}

{author_name} updated their avatar to a new image.

The avatar reflects their evolving identity within the community.
"""
        event_type = "avatar_update"
    
    elif cmd_type == "bio":
        title = f"{author_name} Updated Bio"
        bio_text = params.get("bio", "")
        content = f"""# {title}

{author_name} updated their bio:

> {bio_text}

This helps us better understand their background and interests.
"""
        event_type = "bio_update"
    
    elif cmd_type == "interests":
        title = f"{author_name} Updated Interests"
        interests_text = params.get("interests", "")
        content = f"""# {title}

{author_name} updated their interests: {interests_text}

These interests help shape the topics and themes in our discussions.
"""
        event_type = "interests_update"
    
    else:
        title = f"{author_name} System Event"
        content = f"# {title}\n\n{author_name} triggered a system event: {cmd_type}"
        event_type = "system_event"
    
    # Create slug from title and date
    slug = f"{date}-{event_type}-{author_uuid[:8]}"
    
    # Create ANNOUNCEMENT document
    return Document(
        content=content,
        type=DocumentType.ANNOUNCEMENT,
        metadata={
            "title": title,
            "slug": slug,
            "authors": [
                {"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}
            ],
            "event_type": event_type,
            "actor": author_uuid,
            "date": date
        }
    )
