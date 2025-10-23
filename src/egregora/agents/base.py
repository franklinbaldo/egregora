from abc import ABC, abstractmethod
from typing import Any
import logging
from google import genai
from ..tools.registry import ToolRegistry


logger = logging.getLogger(__name__)


class Agent(ABC):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        tools: ToolRegistry | None = None,
    ):
        self.model = model
        self.client = genai.Client(api_key=api_key)
        self.tools = tools or ToolRegistry()
        self.memory: list[dict[str, Any]] = []

    async def call_llm(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.models.generate_content(
            model=self.model,
            contents=messages,
        )
        return response.text

    def add_memory(self, key: str, value: Any):
        self.memory.append({"key": key, "value": value})

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass
