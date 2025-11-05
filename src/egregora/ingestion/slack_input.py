"""Slack input source implementation (TEMPLATE/EXAMPLE).

This is a template showing how to implement a new input source.
To complete this implementation, you would need to:
1. Install slack-sdk: pip install slack-sdk
2. Obtain Slack API credentials
3. Implement the parsing logic based on Slack's export format

This template demonstrates the interface that needs to be implemented.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import ibis
from ibis.expr.types import Table

from ..core.input_source import InputMetadata, InputSource

logger = logging.getLogger(__name__)


class SlackInputSource(InputSource):
    """Slack input source for JSON exports.

    Parses Slack export directories (exported from Slack workspace settings).
    Slack exports are structured as:
    - channel_name/YYYY-MM-DD.json (one file per day per channel)
    - users.json (user information)
    - channels.json (channel metadata)

    Note: This is a template implementation. To use it, you need to:
    1. Export your Slack workspace data
    2. Extract the ZIP to a directory
    3. Pass the directory path to parse()
    """

    @property
    def source_type(self) -> str:
        """Return 'slack' as the source type identifier."""
        return "slack"

    def supports_format(self, source_path: Path) -> bool:
        """Check if the path is a valid Slack export directory.

        Args:
            source_path: Path to check

        Returns:
            True if it's a directory containing channels.json and users.json
        """
        if not source_path.exists():
            return False

        if not source_path.is_dir():
            return False

        # Check for Slack export markers
        channels_file = source_path / "channels.json"
        users_file = source_path / "users.json"

        return channels_file.exists() and users_file.exists()

    def parse(
        self,
        source_path: Path,
        channel_name: str | None = None,
        export_date: date | None = None,
        timezone: Any = None,
        **kwargs,
    ) -> tuple[Table, InputMetadata]:
        """Parse Slack export directory into standardized Ibis Table.

        Args:
            source_path: Path to the extracted Slack export directory
            channel_name: Optional specific channel to parse (if None, parse all)
            export_date: Optional export date (defaults to today)
            timezone: Optional timezone (defaults to UTC)
            **kwargs: Additional options

        Returns:
            tuple of (messages_table, metadata)

        Raises:
            ValueError: If source_path is not a valid Slack export
            RuntimeError: If parsing fails
            NotImplementedError: This is a template - full implementation needed
        """
        if not self.supports_format(source_path):
            raise ValueError(f"Source path {source_path} is not a valid Slack export directory")

        # Load users for name mapping
        users = self._load_users(source_path)

        # Find all channel directories
        channels = self._find_channels(source_path)

        if channel_name:
            # Filter to specific channel
            channels = [c for c in channels if c["name"] == channel_name]
            if not channels:
                raise ValueError(f"Channel '{channel_name}' not found in export")

        # Parse messages from all channels
        all_messages = []
        for channel in channels:
            messages = self._parse_channel(source_path, channel, users)
            all_messages.extend(messages)

        if not all_messages:
            logger.warning("No messages found in Slack export")
            from ..core.schema import MESSAGE_SCHEMA

            empty_table = ibis.memtable([], schema=ibis.schema(MESSAGE_SCHEMA))
            metadata = InputMetadata(
                source_type=self.source_type,
                group_name=channel_name or "Slack Export",
                group_slug=self._slugify(channel_name or "slack-export"),
                export_date=export_date or date.today(),
                timezone=str(timezone) if timezone else "UTC",
            )
            return empty_table, metadata

        # Create Ibis table
        table = ibis.memtable(all_messages)

        # Sort by timestamp
        table = table.order_by("timestamp")

        # Create metadata
        metadata = InputMetadata(
            source_type=self.source_type,
            group_name=channel_name or "Slack Export",
            group_slug=self._slugify(channel_name or "slack-export"),
            export_date=export_date or date.today(),
            timezone=str(timezone) if timezone else "UTC",
            additional_metadata={
                "channel_count": len(channels),
                "message_count": len(all_messages),
            },
        )

        return table, metadata

    def extract_media(
        self,
        source_path: Path,
        output_dir: Path,
        **kwargs,
    ) -> dict[str, str]:
        """Extract media files from Slack export.

        Slack exports don't include media files directly - files are referenced
        by URL. This would need to download files from Slack API.

        Args:
            source_path: Path to the Slack export directory
            output_dir: Directory to save media files to
            **kwargs: Additional options (e.g., slack_token for API access)

        Returns:
            Mapping of original URL -> local file path

        Raises:
            NotImplementedError: This is a template - full implementation needed
        """
        # TODO: Implement media download using Slack API
        # This would require:
        # 1. Scanning messages for file attachments
        # 2. Using Slack API with token to download files
        # 3. Saving files to output_dir/media/
        logger.warning("Slack media extraction not implemented - files will remain as URLs")
        return {}

    def _load_users(self, source_path: Path) -> dict[str, dict[str, Any]]:
        """Load users.json and create ID -> user info mapping."""
        users_file = source_path / "users.json"
        if not users_file.exists():
            return {}

        with users_file.open("r", encoding="utf-8") as f:
            users_list = json.load(f)

        # Create mapping: user_id -> {name, real_name, display_name}
        users_map = {}
        for user in users_list:
            user_id = user.get("id")
            if user_id:
                profile = user.get("profile", {})
                users_map[user_id] = {
                    "name": user.get("name", "Unknown"),
                    "real_name": profile.get("real_name", "Unknown"),
                    "display_name": profile.get("display_name", "Unknown"),
                }

        return users_map

    def _find_channels(self, source_path: Path) -> list[dict[str, Any]]:
        """Find all channel directories in the export."""
        channels_file = source_path / "channels.json"
        if not channels_file.exists():
            return []

        with channels_file.open("r", encoding="utf-8") as f:
            channels = json.load(f)

        # Filter to channels that have message files
        valid_channels = []
        for channel in channels:
            channel_dir = source_path / channel["name"]
            if channel_dir.exists() and channel_dir.is_dir():
                valid_channels.append(channel)

        return valid_channels

    def _parse_channel(
        self,
        source_path: Path,
        channel: dict[str, Any],
        users: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Parse all messages from a single channel."""
        channel_name = channel["name"]
        channel_dir = source_path / channel_name

        if not channel_dir.exists():
            return []

        messages = []

        # Process all JSON files in channel directory (one per day)
        for json_file in sorted(channel_dir.glob("*.json")):
            with json_file.open("r", encoding="utf-8") as f:
                day_messages = json.load(f)

            for msg in day_messages:
                parsed = self._parse_message(msg, channel_name, users)
                if parsed:
                    messages.append(parsed)

        return messages

    def _parse_message(
        self,
        msg: dict[str, Any],
        channel_name: str,
        users: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Parse a single Slack message into MESSAGE_SCHEMA format."""
        # Skip non-message types
        msg_type = msg.get("type")
        if msg_type != "message":
            return None

        # Skip bot messages and system messages
        if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
            return None

        # Get timestamp (Slack uses Unix timestamp as string)
        ts = msg.get("ts")
        if not ts:
            return None

        try:
            timestamp = datetime.fromtimestamp(float(ts), tz=UTC)
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp: {ts}")
            return None

        # Get author
        user_id = msg.get("user", "Unknown")
        user_info = users.get(user_id, {})
        author = user_info.get("display_name") or user_info.get("name", user_id)

        # Get message text
        text = msg.get("text", "")

        # Handle file attachments (TODO: download files)
        files = msg.get("files", [])
        if files:
            for file in files:
                file_name = file.get("name", "file")
                file_url = file.get("url_private", "")
                text += f"\n[File: {file_name}]({file_url})"

        # Create message ID (use timestamp + user)
        message_id = f"{ts}_{user_id}"

        return {
            "timestamp": timestamp,
            "date": timestamp.date(),
            "author": author,
            "message": text,
            "original_line": json.dumps(msg),  # Store raw JSON for debugging
            "tagged_line": text,
            "message_id": message_id,
        }

    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        import re

        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = text.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug
