import logging
import re
import json
from typing import Pattern

from pydantic import BaseModel
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from egregora.config import EgregoraConfig, get_google_api_key
from egregora.resources.prompts import render_prompt

logger = logging.getLogger(__name__)


class ParserDefinition(BaseModel):
    regex_pattern: str


def generate_dynamic_regex(sample_lines: list[str], config: EgregoraConfig) -> Pattern | None:
    """
    Uses LLM to generate a regex pattern matching the specific locale of the input file.
    """
    if not sample_lines:
        return None

    api_key = get_google_api_key()
    if not api_key:
        logger.warning("GOOGLE_API_KEY not found. Skipping dynamic parser generation.")
        return None

    genai.configure(api_key=api_key)

    prompt = render_prompt("parser_generator.jinja", sample_lines="\n".join(sample_lines))

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        generation_config = GenerationConfig(response_mime_type="application/json")

        response = model.generate_content(
            prompt,
            generation_config=generation_config,
        )

        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]

        data = json.loads(text)
        result = ParserDefinition.model_validate(data)

        if not result or not result.regex_pattern:
            return None

        logger.info(f"LLM generated dynamic regex: {result.regex_pattern}")

        pattern = re.compile(result.regex_pattern)

        matches = 0
        for line in sample_lines:
            if pattern.match(line):
                matches += 1

        if matches / len(sample_lines) >= 0.5:
            return pattern
        else:
            logger.warning(f"Generated regex failed validation (matched {matches}/{len(sample_lines)} lines)")
            return None

    except Exception as e:
        logger.error(f"Failed to generate dynamic parser: {e}")
        return None
