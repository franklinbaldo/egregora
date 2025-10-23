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
from .site_scaffolding import ensure_mkdocs_project


console = Console()
logger = logging.getLogger(__name__)


class EgregoraCLI:
    """Egregora v2 - Ultra-simple WhatsApp to blog pipeline"""

    def init(self, output_dir: str):
        """
        Initialize a new MkDocs site scaffold for serving Egregora posts.

        Creates:
        - mkdocs.yml with Material theme + blog plugin
        - Directory structure (docs/, posts/, profiles/, media/)
        - README.md with quick start instructions
        - .gitignore for Python and MkDocs
        - Starter pages (homepage, about, profiles index)

        Args:
            output_dir: Directory path for the new site (e.g., 'my-blog')
        """
        site_root = Path(output_dir).resolve()
        docs_dir, mkdocs_created = ensure_mkdocs_project(site_root)

        if mkdocs_created:
            console.print(
                Panel(
                    f"[bold green]✅ MkDocs site scaffold initialized successfully![/bold green]\n\n"
                    f"📁 Site root: {site_root}\n"
                    f"📝 Docs directory: {docs_dir}\n\n"
                    f"[bold]Next steps:[/bold]\n"
                    f"• Install MkDocs: [cyan]pip install 'mkdocs-material[imaging]'[/cyan]\n"
                    f"• Change to site directory: [cyan]cd {output_dir}[/cyan]\n"
                    f"• Serve the site: [cyan]mkdocs serve[/cyan]\n"
                    f"• Process WhatsApp export: [cyan]egregora process --zip_file=export.zip --output={output_dir}[/cyan]",
                    title="🛠️ Initialization Complete",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    f"[bold yellow]⚠️ MkDocs site already exists at {site_root}[/bold yellow]\n\n"
                    f"📁 Using existing setup:\n"
                    f"• Docs directory: {docs_dir}\n\n"
                    f"[bold]To update or regenerate:[/bold]\n"
                    f"• Manually edit [cyan]mkdocs.yml[/cyan] or remove it to reinitialize.",
                    title="📁 Site Exists",
                    border_style="yellow",
                )
            )

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
        Process WhatsApp export and generate blog posts + author profiles.

        The LLM decides:
        - What's worth writing about (filters noise automatically)
        - How many posts per period (0-N)
        - All metadata (title, slug, tags, summary, etc)
        - Which author profiles to update based on contributions

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

            total_posts = sum(len(result["posts"]) for result in results.values())
            total_profiles = sum(len(result["profiles"]) for result in results.values())

            console.print(
                Panel(
                    f"[bold green]✓ Processing complete![/bold green]\n\n"
                    f"Periods processed: {len(results)}\n"
                    f"Posts created: {total_posts}\n"
                    f"Profiles updated: {total_profiles}\n\n"
                    f"Output directory: {output_dir}/posts/\n"
                    f"Profiles directory: {output_dir}/profiles/\n"
                    f"Enriched data: {output_dir}/enriched/",
                    title="Success",
                    border_style="green",
                )
            )

            if total_posts > 0 or total_profiles > 0:
                if total_posts > 0:
                    console.print("\n[bold]Posts created:[/bold]")
                    for period_key, result in results.items():
                        if result["posts"]:
                            console.print(f"\n[cyan]{period_key}:[/cyan]")
                            for post in result["posts"]:
                                console.print(f"  • {Path(post).name}")

                if total_profiles > 0:
                    console.print("\n[bold]Profiles updated:[/bold]")
                    unique_profiles = set()
                    for result in results.values():
                        unique_profiles.update(result["profiles"])
                    for profile in sorted(unique_profiles):
                        console.print(f"  • {Path(profile).name}")

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
