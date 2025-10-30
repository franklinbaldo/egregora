import logging
from typing import Any, Optional

from .console import Console


class RichHandler(logging.Handler):
    markup: bool
    show_path: bool
    console: Optional[Console]

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
