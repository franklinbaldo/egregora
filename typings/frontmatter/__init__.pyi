from typing import Any, Mapping, Protocol, TextIO

class Post(Protocol):
    metadata: Mapping[str, Any]
    content: str

def load(fp: TextIO) -> Post: ...
