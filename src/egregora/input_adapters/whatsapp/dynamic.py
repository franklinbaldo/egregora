import logging
import re
from re import Pattern

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError

from egregora.config import EgregoraConfig
from egregora.resources.prompts import render_prompt

logger = logging.getLogger(__name__)


class ParserDefinition(BaseModel):
    regex_pattern: str = Field(
        ...,
        description="The Python regex pattern to parse a chat log line.",
    )


def generate_dynamic_regex(sample_lines: list[str], config: EgregoraConfig) -> Pattern | None:
    """Uses a pydantic-ai Agent to generate a regex pattern for the input file."""
    if not sample_lines:
        return None

    # Use the same model as the other agents for consistency
    system_prompt = render_prompt("parser_generator_system.jinja")
    user_prompt = render_prompt("parser_generator_user.jinja", sample_lines="\n".join(sample_lines))

    agent = Agent(config.models.enricher, system_prompt=system_prompt)

    min_match_ratio = 0.5

    try:
        result = agent.run_sync(user_prompt)

        if hasattr(result, "data"):
            data = result.data
        elif hasattr(result, "output"):
            data = result.output
        else:
            data = result

        if not data or not data.regex_pattern:
            return None

        logger.info("LLM generated dynamic regex: %s", data.regex_pattern)

        # COMPILATION & VERIFICATION STEP
        pattern = re.compile(data.regex_pattern)

        matches = 0
        for line in sample_lines:
            if pattern.match(line):
                matches += 1

        # If it matches at least 50% of the sample lines, accept it
        if matches / len(sample_lines) >= min_match_ratio:
            return pattern
        logger.warning(
            "Generated regex failed validation (matched %d/%d lines)",
            matches,
            len(sample_lines),
        )
        return None  # noqa: TRY300

    except AgentRunError:
        logger.exception("Agent run failed during dynamic parser generation")
        return None
    except Exception:
        logger.exception("Failed to generate or validate dynamic parser")
        return None
