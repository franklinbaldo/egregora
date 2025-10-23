import asyncio
import logging
import os
from pathlib import Path
import fire
from rich.console import Console
from rich.logging import RichHandler

from .core.config import PipelineConfig, LLMConfig
from .pipeline import Pipeline
from .pipeline.loader import load_messages_from_zip


console = Console()
logger = logging.getLogger(__name__)


class EgregoraCLI:
    """Egregora v2 - Agent-based WhatsApp to blog pipeline"""

    def process(
        self,
        zip_file: str,
        output: str = "output",
        gemini_key: str | None = None,
        enable_rag: bool = False,
        enable_profiler: bool = False,
        debug: bool = False,
    ):
        """Process WhatsApp export and generate posts.

        Args:
            zip_file: Path to WhatsApp export ZIP
            output: Output directory for posts
            gemini_key: Google Gemini API key
            enable_rag: Enable RAG enrichment
            enable_profiler: Enable profile generation
            debug: Enable debug logging
        """
        if debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(message)s",
                handlers=[RichHandler(console=console)],
            )
        else:
            logging.basicConfig(
                level=logging.INFO,
                format="%(message)s",
                handlers=[RichHandler(console=console, show_path=False)],
            )

        if gemini_key:
            os.environ["GOOGLE_API_KEY"] = gemini_key
        elif not os.getenv("GOOGLE_API_KEY"):
            console.print("[red]Error: GOOGLE_API_KEY required[/red]")
            return

        config = PipelineConfig(
            input_dir=Path(zip_file).parent,
            output_dir=Path(output),
            llm=LLMConfig(api_key=os.getenv("GOOGLE_API_KEY")),
        )
        config.enricher.enable_rag = enable_rag
        config.profiler.enabled = enable_profiler

        asyncio.run(self._run_pipeline(config, Path(zip_file)))

    async def _run_pipeline(self, config: PipelineConfig, zip_path: Path):
        console.print(f"[cyan]Loading messages from {zip_path}...[/cyan]")

        messages_by_date = load_messages_from_zip(zip_path)

        console.print(f"[green]Found {len(messages_by_date)} days of messages[/green]")

        pipeline = Pipeline(config)

        for date, messages in sorted(messages_by_date.items()):
            console.print(f"\n[cyan]Processing {date} ({len(messages)} messages)...[/cyan]")

            try:
                post = await pipeline.run(messages, date)
                pipeline.save_post(post)
                console.print(f"[green]✓ Generated post for {date}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Failed for {date}: {e}[/red]")
                if config.llm.api_key:
                    logger.exception("Pipeline error")

        if config.profiler.enabled:
            all_messages = []
            for msgs in messages_by_date.values():
                all_messages.extend(msgs)

            profiles = await pipeline.generate_profiles(all_messages)
            console.print(f"\n[green]Generated {len(profiles)} profiles[/green]")


def main():
    fire.Fire(EgregoraCLI)


if __name__ == "__main__":
    main()
