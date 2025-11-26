from __future__ import annotations

from typing import TYPE_CHECKING

from llama_index.core.tools import FunctionTool

from egregora.agents.tools.definitions import read_profile_tool, write_post_tool
from egregora.agents.writer import PostMetadata, ReadProfileResult, WritePostResult

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from egregora.agents.writer import WriterDeps


def create_writer_tools(
    ctx: RunContext[WriterDeps],
) -> list[FunctionTool]:
    """Create LlamaIndex FunctionTools for the writer agent."""

    def write_post_wrapper(metadata: dict, content: str) -> WritePostResult:
        post_metadata = PostMetadata(**metadata)
        return write_post_tool(ctx, post_metadata, content)

    def read_profile_wrapper(author_uuid: str) -> ReadProfileResult:
        return read_profile_tool(ctx, author_uuid)

    write_post = FunctionTool.from_defaults(
        fn=write_post_wrapper,
        name="write_post_tool",
        description="Writes a new blog post.",
    )
    read_profile = FunctionTool.from_defaults(
        fn=read_profile_wrapper,
        name="read_profile_tool",
        description="Reads an author's profile.",
    )

    return [write_post, read_profile]
