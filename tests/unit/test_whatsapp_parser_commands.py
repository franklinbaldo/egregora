from __future__ import annotations

from datetime import UTC, datetime

import ibis

from egregora.input_adapters.whatsapp.parser import extract_commands


def test_extract_commands_handles_plain_and_smart_quotes() -> None:
    messages = ibis.memtable(
        [
            {
                "author": "alice",
                "timestamp": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
                "message": '/egregora set alias "Frank"',
            },
            {
                "author": "bob",
                "timestamp": datetime(2024, 1, 1, 12, 1, tzinfo=UTC),
                "message": "/egregora set alias “Franklin”",
            },
            {
                "author": "carol",
                "timestamp": datetime(2024, 1, 1, 12, 2, tzinfo=UTC),
                "message": "hello there",
            },
        ]
    )

    commands = extract_commands(messages)

    assert len(commands) == 2
    assert commands == [
        {
            "author": "alice",
            "timestamp": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            "message": '/egregora set alias "Frank"',
            "command": {"command": "set", "target": "alias", "value": "Frank"},
        },
        {
            "author": "bob",
            "timestamp": datetime(2024, 1, 1, 12, 1, tzinfo=UTC),
            "message": "/egregora set alias “Franklin”",
            "command": {"command": "set", "target": "alias", "value": "Franklin"},
        },
    ]
