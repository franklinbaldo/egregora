"""Economic mode execution for the writer agent.

This module provides a lighter-weight execution path that bypasses full agent tool loops
in favor of single-shot generation, suitable for summaries or cost-saving modes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from google import genai
from google.genai import types

from egregora.agents.types import WriterDeps
from egregora.data_primitives.document import Document, DocumentType

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)


def execute_economic_writer(
    prompt: str,
    config: EgregoraConfig,
    deps: WriterDeps,
) -> tuple[list[str], list[str]]:
    """Execute writer in economic mode (one-shot, no tools, no streaming)."""
    # 1. Create simple model for generation
    model_name = config.models.writer
    # Handle pydantic-ai prefix
    if model_name.startswith("google-gla:"):
        model_name = model_name.replace("google-gla:", "models/")

    # We use genai directly for simple generation to bypass pydantic-ai overhead/tools
    # Or we can use pydantic-ai agent without tools.
    # Let's use pydantic-ai agent without tools for consistency in dependency injection if needed,
    # BUT the user asked for "content generation instead of streaming" and "avoid tool usage".

    # Simple approach: Use genai.Client directly if available in deps, or creating one.
    # deps.resources.client should be a genai.Client
    client = deps.resources.client
    if not client:
        # Fallback creation if not in deps
        client = genai.Client()

    # We need to render system instructions (including RAG etc)
    # The current prompt variable contains the USER prompt (conversation XML).
    # We need the system instructions.

    # In full agent mode, system prompts are dynamic.
    # Here we should probably construct a simple system instruction or use the configured override.
    system_instruction = config.writer.economic_system_instruction
    if not system_instruction:
        system_instruction = (
            "You are an expert blog post writer. "
            "Analyze the provided conversation log and write a blog post summarizing it. "
            "Return ONLY the markdown content of the post. "
            "Do not use any tools."
        )

    # Add custom instructions if available (append to base/override instruction)
    if deps.config and deps.config.writer.custom_instructions:
        system_instruction += f"\n\n{deps.config.writer.custom_instructions}"

    temperature = config.writer.economic_temperature

    logger.info("Generating content (Economic Mode, temp=%.1f)...", temperature)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
            ),
        )

        content = response.text or ""

        # Extract title from content if possible
        title = f"Summary: {deps.window_start.strftime('%Y-%m-%d')}"
        lines = content.strip().splitlines()
        if lines and lines[0].startswith("# "):
            potential_title = lines[0][2:].strip()
            if potential_title:
                title = potential_title

        # Save content as a post
        # We need to manually create a document since we aren't using the tool
        # Generate a slug/filename
        slug = f"{deps.window_start.strftime('%Y-%m-%d')}-summary"

        doc = Document(
            content=content,
            type=DocumentType.POST,
            metadata={
                "slug": slug,
                "date": deps.window_start.strftime("%Y-%m-%d"),
                "title": title,
            },
            source_window=deps.window_label,
        )

        deps.resources.output.persist(doc)
        logger.info("Saved economic post: %s", doc.document_id)

        return [doc.document_id], []

    except Exception as e:
        logger.exception("Economic writer failed")
        msg = f"Economic writer failed: {e}"
        raise RuntimeError(msg) from e
