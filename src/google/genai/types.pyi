from __future__ import annotations

from typing import Any, Sequence

class Type:
    OBJECT: str
    STRING: str
    ARRAY: str
    INTEGER: str
    NUMBER: str
    BOOLEAN: str

class Schema:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class FunctionDeclaration:
    name: str
    description: str | None
    parameters: Any
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Tool:
    function_declarations: Sequence[FunctionDeclaration]
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class FunctionCall:
    name: str
    args: Any
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class FunctionResponse:
    name: str
    response: Any
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Part:
    text: str | None
    function_call: FunctionCall | None
    function_response: FunctionResponse | None
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Content:
    role: str
    parts: Sequence[Part]
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Candidate:
    content: Content
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class GenerateContentResponse:
    candidates: Sequence[Candidate]
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class GenerateContentConfig:
    tools: Sequence[Tool] | None
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
