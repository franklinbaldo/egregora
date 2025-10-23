"""Simple CLI for Egregora v2."""

import asyncio
import logging
import os
from pathlib import Path
import fire
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from .pipeline import process_whatsapp_export


console = Console()
logger = logging.getLogger(__name__)


class EgregoraCLI:
    """Egregora v2 - Ultra-simple WhatsApp to blog pipeline"""

    def process(
        self,
        zip_file: str,
        output: str = "output",
        period: str = "day",
        enable_enrichment: bool = True,
        gemini_key: str | None = None,
        debug: bool = False,
    ):
        """
        Process WhatsApp export and generate blog posts.

        The LLM decides:
        - What's worth writing about (filters noise automatically)
        - How many posts per period (0-N)
        - All metadata (title, slug, tags, summary, etc)

        Args:
            zip_file: Path to WhatsApp export ZIP
            output: Output directory
            period: Group by "day", "week", or "month"
            enable_enrichment: Add URL/media context
            gemini_key: Google Gemini API key
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
            console.print(
                Panel(
                    "[red]Error: GOOGLE_API_KEY required[/red]\n\n"
                    "Get your key: https://aistudio.google.com/app/apikey\n\n"
                    "Then either:\n"
                    "• Use --gemini_key flag\n"
                    "• Set GOOGLE_API_KEY environment variable",
                    title="API Key Required",
                    border_style="red",
                )
            )
            return

        asyncio.run(
            self._run_pipeline(
                Path(zip_file),
                Path(output),
                period,
                enable_enrichment,
                os.getenv("GOOGLE_API_KEY"),
            )
        )

    async def _run_pipeline(
        self,
        zip_path: Path,
        output_dir: Path,
        period: str,
        enable_enrichment: bool,
        api_key: str,
    ):
        """Run the async pipeline."""

        console.print(f"\n[cyan]Processing {zip_path}...[/cyan]\n")

        try:
            results = await process_whatsapp_export(
                zip_path=zip_path,
                output_dir=output_dir,
                period=period,
                enable_enrichment=enable_enrichment,
                gemini_api_key=api_key,
            )

            total_posts = sum(len(posts) for posts in results.values())

            console.print(
                Panel(
                    f"[bold green]✓ Processing complete![/bold green]\n\n"
                    f"Periods processed: {len(results)}\n"
                    f"Posts created: {total_posts}\n\n"
                    f"Output directory: {output_dir}/posts/\n"
                    f"Enriched data: {output_dir}/enriched/",
                    title="Success",
                    border_style="green",
                )
            )

            if total_posts > 0:
                console.print("\n[bold]Posts created:[/bold]")
                for period_key, posts in results.items():
                    if posts:
                        console.print(f"\n[cyan]{period_key}:[/cyan]")
                        for post in posts:
                            console.print(f"  • {Path(post).name}")

        except Exception as e:
            console.print(
                Panel(
                    f"[red]Error: {str(e)}[/red]",
                    title="Processing Failed",
                    border_style="red",
                )
            )
            if logger.level == logging.DEBUG:
                raise


def main():
    fire.Fire(EgregoraCLI)


if __name__ == "__main__":
    main()
