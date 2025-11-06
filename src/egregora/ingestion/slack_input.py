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
from typing import TYPE_CHECKING, Any

import ibis

from egregora.ingestion.base import InputMetadata, InputSource

if TYPE_CHECKING:
    from pathlib import Path

    from ibis.expr.types import Table
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
        channels_file = source_path / "channels.json"
        users_file = source_path / "users.json"
        return channels_file.exists() and users_file.exists()

    def parse(
        self,
        source_path: Path,
        channel_name: str | None = None,
        export_date: date | None = None,
        timezone: str | None = None,
        **_kwargs: Any,
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
            msg = f"Source path {source_path} is not a valid Slack export directory"
            raise ValueError(msg)
        users = self._load_users(source_path)
        channels = self._find_channels(source_path)
        if channel_name:
            channels = [c for c in channels if c["name"] == channel_name]
            if not channels:
                msg = f"Channel '{channel_name}' not found in export"
                raise ValueError(msg)
        all_messages = []
        for channel in channels:
            messages = self._parse_channel(source_path, channel, users)
            all_messages.extend(messages)
        if not all_messages:
            logger.warning("No messages found in Slack export")
            from egregora.schema import MESSAGE_SCHEMA

            empty_table = ibis.memtable([], schema=ibis.schema(MESSAGE_SCHEMA))
            metadata = InputMetadata(
                source_type=self.source_type,
                group_name=channel_name or "Slack Export",
                group_slug=self._slugify(channel_name or "slack-export"),
                export_date=export_date or date.today(),
                timezone=str(timezone) if timezone else "UTC",
            )
            return (empty_table, metadata)
        table = ibis.memtable(all_messages)
        table = table.order_by("timestamp")
        metadata = InputMetadata(
            source_type=self.source_type,
            group_name=channel_name or "Slack Export",
            group_slug=self._slugify(channel_name or "slack-export"),
            export_date=export_date or date.today(),
            timezone=str(timezone) if timezone else "UTC",
            additional_metadata={"channel_count": len(channels), "message_count": len(all_messages)},
        )
        return (table, metadata)

    def extract_media(self, _source_path: Path, _output_dir: Path, **_kwargs: Any) -> dict[str, str]:
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
        logger.warning("Slack media extraction not implemented - files will remain as URLs")
        return {}

    def _load_users(self, source_path: Path) -> dict[str, dict[str, Any]]:
        """Load users.json and create ID -> user info mapping."""
        users_file = source_path / "users.json"
        if not users_file.exists():
            return {}
        with users_file.open("r", encoding="utf-8") as f:
            users_list = json.load(f)
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
        valid_channels = []
        for channel in channels:
            channel_dir = source_path / channel["name"]
            if channel_dir.exists() and channel_dir.is_dir():
                valid_channels.append(channel)
        return valid_channels

    def _parse_channel(
        self, source_path: Path, channel: dict[str, Any], users: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Parse all messages from a single channel."""
        channel_name = channel["name"]
        channel_dir = source_path / channel_name
        if not channel_dir.exists():
            return []
        messages = []
        for json_file in sorted(channel_dir.glob("*.json")):
            with json_file.open("r", encoding="utf-8") as f:
                day_messages = json.load(f)
            for msg in day_messages:
                parsed = self._parse_message(msg, channel_name, users)
                if parsed:
                    messages.append(parsed)
        return messages

    def _parse_message(
        self, msg: dict[str, Any], _channel_name: str, users: dict[str, dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Parse a single Slack message into MESSAGE_SCHEMA format."""
        msg_type = msg.get("type")
        if msg_type != "message":
            return None
        if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
            return None
        ts = msg.get("ts")
        if not ts:
            return None
        try:
            timestamp = datetime.fromtimestamp(float(ts), tz=UTC)
        except (ValueError, TypeError):
            logger.warning("Invalid timestamp: %s", ts)
            return None
        user_id = msg.get("user", "Unknown")
        user_info = users.get(user_id, {})
        author = user_info.get("display_name") or user_info.get("name", user_id)
        text = msg.get("text", "")
        files = msg.get("files", [])
        if files:
            for file in files:
                file_name = file.get("name", "file")
                file_url = file.get("url_private", "")
                text += f"\n[File: {file_name}]({file_url})"
        message_id = f"{ts}_{user_id}"
        return {
            "timestamp": timestamp,
            "date": timestamp.date(),
            "author": author,
            "message": text,
            "original_line": json.dumps(msg),
            "tagged_line": text,
            "message_id": message_id,
        }

    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        import re

        slug = text.lower()
        slug = re.sub("[^a-z0-9]+", "-", slug)
        return slug.strip("-")
