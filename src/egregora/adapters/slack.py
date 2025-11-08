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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypedDict

import ibis

from egregora.pipeline.adapters import MediaMapping, SourceAdapter
from egregora.pipeline.ir import IR_SCHEMA, create_ir_table

if TYPE_CHECKING:
    from pathlib import Path

    from ibis.expr.types import Table


class _EmptyKwargs(TypedDict):
    """Empty TypedDict for unused kwargs in adapter methods."""


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

    def parse(self, input_path: Path, *, timezone: str | None = None, **_kwargs: _EmptyKwargs) -> Table:
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
        msg = (
            "Slack adapter is not yet implemented. "
            "This is a stub for demonstration purposes.\n\n"
            "To add Slack support:\n"
            "1. Implement SlackAdapter.parse() to read Slack JSON export format\n"
            "2. Map Slack message fields to IR v1 schema\n"
            "3. Add tests for Slack-specific parsing logic\n\n"
            "See src/egregora/adapters/whatsapp/ for a complete adapter example."
        )
        raise NotImplementedError(msg)

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
        has_data = False
        if input_path.is_file() and input_path.suffix == ".json":
            try:
                with input_path.open() as f:
                    data = json.load(f)
                    has_data = bool(data)
            except (OSError, json.JSONDecodeError):
                pass
        elif input_path.is_dir():
            has_data = any(input_path.glob("*.json"))
        if has_data:
            logger.warning(
                "⚠️  SlackAdapter is a STUB and returns empty results. To process Slack exports, implement the _parse_slack_json() method."
            )
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
            if msg.get("type") != "message":
                continue
            ts_str = msg.get("ts", "0")
            timestamp = datetime.fromtimestamp(float(ts_str), tz=UTC)
            ir_msg = {
                "timestamp": timestamp,
                "date": timestamp.date(),
                "author": msg.get("user", "unknown"),
                "message": msg.get("text", ""),
                "original_line": json.dumps(msg),
                "tagged_line": json.dumps(msg),
                "message_id": ts_str.replace(".", ""),
            }
            ir_messages.append(ir_msg)
        return ir_messages

    def extract_media(self, _input_path: Path, _output_dir: Path, **_kwargs: _EmptyKwargs) -> MediaMapping:
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

        Raises:
            NotImplementedError: This is a stub implementation

        """
        msg = "Slack adapter media extraction is not yet implemented."
        raise NotImplementedError(msg)

    def get_metadata(self, _input_path: Path, **_kwargs: _EmptyKwargs) -> dict[str, Any]:
        """Extract metadata from Slack export.

        Args:
            input_path: Path to Slack export
            **kwargs: Additional parameters

        Returns:
            Dictionary with channel/workspace metadata

        Raises:
            NotImplementedError: This is a stub implementation

        """
        msg = "Slack adapter metadata extraction is not yet implemented."
        raise NotImplementedError(msg)
