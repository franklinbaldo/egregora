from pathlib import Path

from pydantic import BaseModel, Field

from egregora.constants import WindowUnit


class WriteCommandConfig(BaseModel):
    """Configuration model for the write command."""

    input_file: Path
    output: Path = Field(default_factory=lambda: Path("site"))
    source: str | None = None
    step_size: int = 100
    step_unit: WindowUnit = WindowUnit.MESSAGES
    overlap: float = 0.0
    enable_enrichment: bool = True
    from_date: str | None = None
    to_date: str | None = None
    timezone: str | None = None
    model: str | None = None
    max_prompt_tokens: int = 400000
    use_full_context_window: bool = False
    max_windows: int | None = None
    resume: bool = True
    refresh: str | None = None
    force: bool = False
    debug: bool = False
    options: str | None = None
    smoke_test: bool = False
    exit_on_error: bool = True
