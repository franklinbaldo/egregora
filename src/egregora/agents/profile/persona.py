"""Persona extraction agent."""

from __future__ import annotations

import logging

from pydantic_ai import Agent

from egregora.agents.profile.models import PersonaModel

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a behavioral psychologist and expert profiler.

Your task is to analyze the provided message history of a single user and extract a structured "Persona Profile".
This profile will be used to simulate this user in a conversation, so accuracy of "voice" and "mindset" is critical.

Focus on:
1. **Communication Style:** specific tics, formatting, verbosity, emotional tone.
2. **Core Values:** what do they fight for? (e.g. "Simplicity", "Correctness", "Speed").
3. **Argumentation:** how do they disagree?
4. **Topics:** what do they talk about?
5. **Voice Sample:** Write a ONE sentence synthetic message that *perfectly* captures their style.

Be specific. Avoid generic astrological-sign style descriptions.
"""


def create_persona_agent(model_name: str) -> Agent[None, PersonaModel]:
    """Create the persona extraction agent."""
    return Agent(
        model_name,
        output_type=PersonaModel,
        system_prompt=SYSTEM_PROMPT,
    )


async def extract_persona(
    messages: list[str],
    author_name: str,
    model_name: str = "google-gla:gemini-1.5-flash",
) -> PersonaModel:
    """Extract persona from messages."""
    if not messages:
        # Return a generic placeholder if no messages
        return PersonaModel(
            communication_style="Unknown (No history)",
            core_values=["Unknown"],
            argumentation_style="Unknown",
            frequent_topics=["None"],
            voice_sample="I have nothing to say.",
        )

    agent = create_persona_agent(model_name)

    # Prepare prompt
    # Limit messages to reasonable context window if needed, but for now assuming list fits
    # (Caller should handle selection/truncation)
    content_block = "\n".join(f"- {msg}" for msg in messages)

    user_prompt = f"""
    Analyze the following messages from user '{author_name}':

    --- BEGIN MESSAGES ---
    {content_block}
    --- END MESSAGES ---

    Extract the persona profile.
    """

    result = await agent.run(user_prompt)
    return result.output
