from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any

from . import types


class _FakeModel:
    def __init__(self) -> None:
        default_payload = json.dumps(
            {
                "summary": "Stubbed summary from fake Gemini client.",
                "topics": [
                    "Resposta estática para validar integração.",
                    "Utilize FAKE_GEMINI_RESPONSE para customizar.",
                ],
                "actions": [
                    {
                        "description": "Revisar conteúdo compartilhado",
                        "owner": "time",
                    }
                ],
                "relevance": 3,
            },
            ensure_ascii=False,
        )
        self._payload = os.getenv("FAKE_GEMINI_RESPONSE", default_payload)

    def generate_content(self, model: str, contents: Any, config: Any) -> SimpleNamespace:
        part = types.Part.from_text(self._payload)
        content = types.Content(role="user", parts=[part])
        candidate = SimpleNamespace(content=content)
        return SimpleNamespace(text=self._payload, candidates=[candidate])


class Client:
    def __init__(self, api_key: str | None = None, **_: Any) -> None:
        self.api_key = api_key
        self.models = _FakeModel()


__all__ = ["Client", "types"]
