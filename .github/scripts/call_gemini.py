#!/usr/bin/env python3
"""Call Gemini API with fallback models for PR review.

Reads prompt from file and calls Gemini API directly,
bypassing GitHub Actions size limitations.
"""

import json
import os
import sys
from pathlib import Path

import google.generativeai as genai


MODELS = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


def call_gemini(prompt: str, api_key: str) -> tuple[str, str, str]:
    """Call Gemini API with fallback models.

    Returns: (outcome, model_used, response_text)
    """
    genai.configure(api_key=api_key)

    for model_name in MODELS:
        try:
            print(f"Trying model: {model_name}...", file=sys.stderr)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)

            if response.text:
                print(f"✓ Success with {model_name}", file=sys.stderr)
                return ("success", model_name, response.text)
            else:
                print(f"✗ Empty response from {model_name}", file=sys.stderr)
                continue

        except Exception as e:
            print(f"✗ Failed with {model_name}: {e}", file=sys.stderr)
            continue

    return ("failure", "none", "All models failed")


def main() -> int:
    """Main entry point."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        return 1

    prompt_file = Path(os.environ.get("PROMPT_FILE", ".github/tmp/prompt.txt"))
    output_file = Path(os.environ.get("OUTPUT_FILE", ".github/tmp/gemini_response.txt"))
    metadata_file = Path(os.environ.get("METADATA_FILE", ".github/tmp/gemini_metadata.json"))

    # Read prompt
    try:
        prompt = prompt_file.read_text(encoding="utf-8")
        print(f"✓ Read prompt ({len(prompt)} chars)", file=sys.stderr)
    except Exception as e:
        print(f"Error reading prompt file: {e}", file=sys.stderr)
        return 1

    # Call Gemini with fallback
    outcome, model_used, response = call_gemini(prompt, api_key)

    # Write outputs
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(response, encoding="utf-8")

        metadata = {
            "outcome": outcome,
            "model": model_used,
            "response_length": len(response),
        }
        metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        print(f"✓ Response written ({len(response)} chars)", file=sys.stderr)
        print(f"✓ Model: {model_used}, Outcome: {outcome}", file=sys.stderr)

    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        return 1

    return 0 if outcome == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
