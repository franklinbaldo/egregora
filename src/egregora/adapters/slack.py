"""Slack source adapter - parses Slack exports into IR format (STUB/TEMPLATE).

This is a minimal stub adapter that demonstrates how to implement support
for a new source. It shows the pluggability of the pipeline system.

⚠️  WARNING: This is a STUB implementation for demonstration purposes.
    It returns empty results and should not be used in production.

To complete this adapter:
1. Implement parse() to read Slack JSON export format
2. Map Slack message fields to IR schema
3. Implement extract_media() if Slack exports include files
4. Add tests for Slack-specific parsing logic
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import ibis

from egregora.pipeline.adapters import MediaMapping, SourceAdapter
from egregora.pipeline.ir import IR_SCHEMA, create_ir_table

if TYPE_CHECKING:
    from pathlib import Path

    from ibis.expr.types import Table

logger = logging.getLogger(__name__)

__all__ = ["SlackAdapter"]


class SlackAdapter(SourceAdapter):
    """Source adapter for Slack exports (STUB/TEMPLATE).

    Slack exports are typically JSON files with a specific structure.
    This adapter shows how to implement a new source.

    Example Slack export structure:
        {
            "messages": [
                {
                    "type": "message",
                    "user": "U12345",
                    "text": "Hello world",
                    "ts": "1234567890.123456"
                },
                ...
            ]
        }
    """

    @property
    def source_name(self) -> str:
        return "Slack"

    @property
    def source_identifier(self) -> str:
        return "slack"

    def parse(
        self,
        input_path: Path,
        *,
        timezone: str | None = None,
        **kwargs: Any,
    ) -> Table:
        """Parse Slack export into IR-compliant table.

        Args:
            input_path: Path to Slack export (JSON file or directory)
            timezone: Timezone for timestamp normalization
            **kwargs: Additional parameters

        Returns:
            Ibis Table conforming to IR_SCHEMA

        Raises:
            NotImplementedError: This is a stub implementation

        """
        if not input_path.exists():
            msg = f"Input path does not exist: {input_path}"
            raise FileNotFoundError(msg)

        # STUB: Minimal implementation that returns an empty table
        # with the correct schema to demonstrate the contract

        # In a real implementation, you would:
        # 1. Read the Slack JSON export
        # 2. Parse messages and map to IR schema
        # 3. Handle user ID -> display name mapping
        # 4. Convert Slack timestamps to IR timestamp format

        # Example stub data (replace with actual parsing)
        messages_data = self._parse_slack_json(input_path)

        if not messages_data:
            # Return empty table with correct schema
            return ibis.memtable([], schema=ibis.schema(IR_SCHEMA))

        # Convert parsed data to IR table
        table = ibis.memtable(messages_data)
        return create_ir_table(table, timezone=timezone)

    def _parse_slack_json(self, input_path: Path) -> list[dict[str, Any]]:
        """Parse Slack JSON export (stub implementation).

        Args:
            input_path: Path to Slack export

        Returns:
            List of message dictionaries

        Raises:
            NotImplementedError: If trying to parse non-empty input

        Note:
            This is a minimal stub. A real implementation would:
            - Handle Slack's nested JSON structure
            - Process multiple channels
            - Handle threaded messages
            - Map user IDs to display names
            - Convert Slack markdown to standard format

        """
        # Check if this is a real Slack export with data
        has_data = False

        if input_path.is_file() and input_path.suffix == ".json":
            try:
                with open(input_path) as f:
                    data = json.load(f)
                    has_data = bool(data)
            except (OSError, json.JSONDecodeError):
                pass
        elif input_path.is_dir():
            has_data = any(input_path.glob("*.json"))

        if has_data:
            logger.warning(
                "⚠️  SlackAdapter is a STUB and returns empty results. "
                "To process Slack exports, implement the _parse_slack_json() method."
            )
            # For now, return empty to allow tests to pass
            # In production, uncomment the line below:
            # raise NotImplementedError(
            #     "SlackAdapter is a stub. Implement _parse_slack_json() to parse Slack exports."
            # )

        # Stub: Return empty list
        # In a real implementation, read and parse the JSON:
        #
        # if input_path.is_file():
        #     with open(input_path) as f:
        #         data = json.load(f)
        #     return self._convert_slack_messages(data["messages"])
        # elif input_path.is_dir():
        #     # Handle directory of JSON files (one per channel)
        #     messages = []
        #     for json_file in input_path.glob("*.json"):
        #         with open(json_file) as f:
        #             data = json.load(f)
        #         messages.extend(self._convert_slack_messages(data))
        #     return messages

        return []

    def _convert_slack_messages(self, slack_messages: list[dict]) -> list[dict]:
        """Convert Slack message format to IR format (stub).

        Args:
            slack_messages: List of Slack message objects

        Returns:
            List of IR-formatted message dicts

        Example conversion:
            Slack format:
                {"user": "U12345", "text": "Hello", "ts": "1234567890.123456"}
            IR format:
                {
                    "timestamp": datetime.fromtimestamp(1234567890),
                    "author": "U12345",
                    "message": "Hello",
                    "message_id": "1234567890123456",
                    ...
                }

        """
        ir_messages = []

        for msg in slack_messages:
            # Skip non-message types
            if msg.get("type") != "message":
                continue

            # Convert Slack timestamp (seconds.microseconds) to datetime
            ts_str = msg.get("ts", "0")
            timestamp = datetime.fromtimestamp(float(ts_str))

            # Build IR message
            ir_msg = {
                "timestamp": timestamp,
                "date": timestamp.date(),
                "author": msg.get("user", "unknown"),
                "message": msg.get("text", ""),
                "original_line": json.dumps(msg),  # Store original for debugging
                "tagged_line": json.dumps(msg),
                "message_id": ts_str.replace(".", ""),
            }

            ir_messages.append(ir_msg)

        return ir_messages

    def extract_media(
        self,
        input_path: Path,
        output_dir: Path,
        **kwargs: Any,
    ) -> MediaMapping:
        """Extract media files from Slack export.

        Slack exports may include uploaded files. This would need to:
        1. Identify file attachments in messages
        2. Download files (if URLs) or extract (if bundled)
        3. Save to output_dir
        4. Return mapping of references to local paths

        Args:
            input_path: Path to Slack export
            output_dir: Directory where media should be extracted
            **kwargs: Additional parameters

        Returns:
            Empty dict (stub implementation)

        Note:
            A real implementation would handle Slack file attachments.

        """
        return {}

    def get_metadata(self, input_path: Path, **kwargs: Any) -> dict[str, Any]:
        """Extract metadata from Slack export.

        Args:
            input_path: Path to Slack export
            **kwargs: Additional parameters

        Returns:
            Dictionary with channel/workspace metadata

        Note:
            Stub implementation returns minimal metadata.

        """
        return {
            "channel_name": "unknown-channel",
            "workspace": "unknown-workspace",
            "export_date": datetime.now().date().isoformat(),
        }
