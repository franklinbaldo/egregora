from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, tool: Tool):
        self._tools[name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    async def execute(self, name: str, **kwargs) -> Any:
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        return await tool.execute(**kwargs)
