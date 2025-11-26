import logging
import re
from typing import Pattern

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.providers.google import GoogleProvider

from egregora.config import EgregoraConfig
from egregora.resources.prompts import render_prompt

logger = logging.getLogger(__name__)


class ParserDefinition(BaseModel):
    regex_pattern: str = Field(
        ...,
        description="The Python regex pattern to parse a chat log line.",
    )


def generate_dynamic_regex(sample_lines: list[str], config: EgregoraConfig) -> Pattern | None:
    """
    Uses a pydantic-ai Agent to generate a regex pattern for the input file.
    """
    if not sample_lines:
        return None

    # Use the same model as the other agents for consistency
    system_prompt = render_prompt("parser_generator_system.jinja")
    user_prompt = render_prompt("parser_generator_user.jinja", sample_lines="\n".join(sample_lines))

    agent = Agent(config.models.enricher, system_prompt=system_prompt)

    try:
        result = agent.run_sync(user_prompt, output_type=ParserDefinition)

        if not result or not result.regex_pattern:
            return None

        logger.info(f"LLM generated dynamic regex: {result.regex_pattern}")

        # COMPILATION & VERIFICATION STEP
        pattern = re.compile(result.regex_pattern)

        matches = 0
        for line in sample_lines:
            if pattern.match(line):
                matches += 1

        # If it matches at least 50% of the sample lines, accept it
        if matches / len(sample_lines) >= 0.5:
            return pattern
        else:
            logger.warning(f"Generated regex failed validation (matched {matches}/{len(sample_lines)} lines)")
            return None

    except AgentRunError as e:
        logger.error(f"Agent run failed during dynamic parser generation: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to generate or validate dynamic parser: {e}")
        return None
