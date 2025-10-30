from types import ModuleType

from .genai import Client


class _GenAIModule(ModuleType):
    Client: type[Client]


genai: _GenAIModule

__all__ = ["genai", "Client"]

