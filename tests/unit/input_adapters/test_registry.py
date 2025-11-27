from unittest.mock import patch

import pytest

from egregora.input_adapters.registry import InputAdapterRegistry
from egregora.input_adapters.whatsapp.adapter import WhatsAppAdapter
from egregora.input_adapters.iperon_tjro import IperonTJROAdapter
from egregora.input_adapters.self_reflection import SelfInputAdapter


@pytest.mark.usefixtures("monkeypatch")
def test_registry_falls_back_to_builtin_adapters(monkeypatch):
    """Registry should provide built-in adapters even if entry points are unavailable."""

    monkeypatch.setattr("egregora.input_adapters.registry.entry_points", lambda group: [])

    registry = InputAdapterRegistry()

    assert isinstance(registry.get("whatsapp"), WhatsAppAdapter)
    assert isinstance(registry.get("iperon-tjro"), IperonTJROAdapter)
    assert isinstance(registry.get("self"), SelfInputAdapter)
    assert len(registry.list_adapters()) == 3
