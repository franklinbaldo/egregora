"""
CLI script to run the Egregora pipeline with API call recording enabled.

This script is used to generate "golden fixtures" for testing. It runs the main
data processing pipeline, but wraps the Gemini API client with a recorder.
This recorder saves all API requests and their corresponding responses to disk.
These saved fixtures can then be used by a mock client in tests to simulate
API calls, making tests fast, deterministic, and free.

Requirements:
- A valid `GOOGLE_API_KEY` must be set as an environment variable.
- You must provide a path to a WhatsApp chat export zip file.
- You must provide an output directory for the generated website.

Usage:
    export GOOGLE_API_KEY="your_api_key_here"
    python scripts/record_golden_fixtures.py \
        --zip-path /path/to/your/whatsapp_chat.zip \
        --output-dir /path/to/output
"""
import logging
import os
import sys
from pathlib import Path
import typer
from typing_extensions import Annotated
import google.generativeai as genai

# Add the project root to the Python path to allow importing from 'egregora'
sys.path.insert(0, str(Path(__file__).parent.parent))

from egregora.orchestration.pipeline import process_whatsapp_export
from egregora.testing.gemini_recorder import GeminiClientRecorder

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command()
def main(
    zip_path: Annotated[
        Path,
        typer.Option(
            "--zip-path",
            "-z",
            help="Path to the WhatsApp chat export zip file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory to save the generated website.",
            file_okay=False,
            dir_okay=True,
            writable=True,
            resolve_path=True,
        ),
    ],
    fixtures_dir: Annotated[
        Path,
        typer.Option(
            "--fixtures-dir",
            "-f",
            help="Directory to save the recorded API fixtures.",
            file_okay=False,
            dir_okay=True,
            writable=True,
            resolve_path=True,
        ),
    ] = Path("tests/fixtures/golden/api_responses"),
):
    """
    Runs the Egregora pipeline and records Gemini API calls to golden fixtures.
    """
    if "GOOGLE_API_KEY" not in os.environ:
        logger.error("The GOOGLE_API_KEY environment variable is not set.")
        logger.error("Please set it to your Google API key to run the recording.")
        raise typer.Exit(code=1)

    logger.info("Starting pipeline with recording enabled.")
    logger.info(f"WhatsApp export: {zip_path}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Fixtures directory: {fixtures_dir}")

    # Configure Gemini API
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    # Monkey-patch genai.Client to return a recorder instead
    # This ensures any Client created by the pipeline will record calls
    _OriginalClient = genai.Client

    def create_recording_client(*args, **kwargs):
        """Factory function that returns a GeminiClientRecorder."""
        real_client = _OriginalClient(*args, **kwargs)
        return GeminiClientRecorder(client=real_client, output_dir=fixtures_dir)

    genai.Client = create_recording_client

    try:
        # Run the main pipeline - it will create its own client which will be recorded
        process_whatsapp_export(
            zip_path=zip_path,
            output_dir=output_dir,
            enable_enrichment=True,  # Ensure all API calls are made
            gemini_api_key=os.environ["GOOGLE_API_KEY"],
        )
        logger.info("Pipeline finished successfully.")
        logger.info(f"Golden fixtures have been recorded to: {fixtures_dir}")

    except Exception as e:
        logger.error(f"An error occurred during the pipeline execution: {e}", exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()