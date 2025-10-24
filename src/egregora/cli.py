"""Simple CLI for Egregora v2."""

import asyncio
import logging
import os
import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fire
from google import genai
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from .editor_agent import run_editor_session
from .model_config import ModelConfig, load_site_config
from .pipeline import process_whatsapp_export
from .ranking.agent import run_comparison
from .ranking.elo import get_posts_to_compare, initialize_ratings, update_ratings
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
        from_date: str | None = None,
        to_date: str | None = None,
        timezone: str | None = None,
        gemini_key: str | None = None,
        model: str | None = None,
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
            from_date: Only process messages from this date onwards (YYYY-MM-DD)
            to_date: Only process messages up to this date (YYYY-MM-DD)
            timezone: IANA timezone (e.g., "America/Sao_Paulo", "America/New_York")
            gemini_key: Google Gemini API key
            model: Gemini model to use (default: gemini-flash, configurable in mkdocs.yml)
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

        # Validate and handle timezone
        timezone_obj = None
        if timezone:
            # Validate timezone
            try:
                timezone_obj = ZoneInfo(timezone)
                logger.info(f"Using timezone: {timezone}")
            except Exception:
                console.print(
                    Panel(
                        f"[red]Invalid timezone: '{timezone}'[/red]\n\n"
                        "Use IANA timezone names (e.g., 'America/Sao_Paulo', 'America/New_York', 'Europe/London')\n\n"
                        f"Find your timezone: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
                        title="Invalid Timezone",
                        border_style="red",
                    )
                )
                return
        else:
            # Show warning when timezone not specified
            console.print(
                Panel(
                    "[yellow]⚠️  No timezone specified - using UTC![/yellow]\n\n"
                    "[bold]WhatsApp exports use your phone's local timezone[/bold]\n\n"
                    "Without the correct timezone:\n"
                    "• Messages may be grouped into wrong dates\n"
                    "• Timestamps will be misinterpreted\n"
                    "• Date filters (--from_date/--to_date) may be inaccurate\n\n"
                    "Examples:\n"
                    "• Brazil (São Paulo): [cyan]--timezone='America/Sao_Paulo'[/cyan]\n"
                    "• USA (New York): [cyan]--timezone='America/New_York'[/cyan]\n"
                    "• UK (London): [cyan]--timezone='Europe/London'[/cyan]\n\n"
                    "Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
                    title="⏰ Timezone Warning",
                    border_style="yellow",
                )
            )
            timezone_obj = ZoneInfo("UTC")

        # Parse and validate date filters

        from_date_obj = None
        to_date_obj = None

        if from_date:
            try:
                from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
            except ValueError:
                console.print(
                    Panel(
                        f"[red]Invalid --from_date: '{from_date}'[/red]\n\n"
                        "Use format: YYYY-MM-DD (e.g., 2025-01-01)",
                        title="Invalid Date",
                        border_style="red",
                    )
                )
                return

        if to_date:
            try:
                to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
            except ValueError:
                console.print(
                    Panel(
                        f"[red]Invalid --to_date: '{to_date}'[/red]\n\n"
                        "Use format: YYYY-MM-DD (e.g., 2025-12-31)",
                        title="Invalid Date",
                        border_style="red",
                    )
                )
                return

        # Validate date range
        if from_date_obj and to_date_obj and from_date_obj > to_date_obj:
            console.print(
                Panel(
                    "[red]Invalid date range![/red]\n\n"
                    f"--from_date ({from_date}) is after --to_date ({to_date})\n\n"
                    "The start date must be before or equal to the end date.",
                    title="Invalid Date Range",
                    border_style="red",
                )
            )
            return

        # Warning when no date filters are set
        if not from_date_obj and not to_date_obj:
            console.print(
                Panel(
                    "[yellow]⚠️  No date filters specified - processing ALL messages![/yellow]\n\n"
                    "[bold]This may be expensive and time-intensive.[/bold]\n\n"
                    "Consider using date filters to reduce cost:\n"
                    f"• --from_date=YYYY-MM-DD  (process from this date onwards)\n"
                    f"• --to_date=YYYY-MM-DD    (process up to this date)\n\n"
                    "Example: Process only messages from January 2025:\n"
                    f"[cyan]egregora process --zip_file={zip_file} --from_date=2025-01-01 --to_date=2025-01-31[/cyan]",
                    title="💰 Cost Warning",
                    border_style="yellow",
                )
            )

        asyncio.run(
            self._run_pipeline(
                Path(zip_file),
                Path(output),
                period,
                enable_enrichment,
                from_date_obj,
                to_date_obj,
                timezone_obj,
                os.getenv("GOOGLE_API_KEY"),
                model,
            )
        )

    async def _run_pipeline(
        self,
        zip_path: Path,
        output_dir: Path,
        period: str,
        enable_enrichment: bool,
        from_date,
        to_date,
        timezone_obj,
        api_key: str,
        model: str | None,
    ):
        """Run the async pipeline."""

        # Build filter message
        filter_msg = ""
        if from_date and to_date:
            filter_msg = f" (filtering: {from_date} to {to_date})"
        elif from_date:
            filter_msg = f" (filtering: from {from_date} onwards)"
        elif to_date:
            filter_msg = f" (filtering: up to {to_date})"

        console.print(f"\n[cyan]Processing {zip_path}{filter_msg}...[/cyan]\n")

        try:
            results = await process_whatsapp_export(
                zip_path=zip_path,
                output_dir=output_dir,
                period=period,
                enable_enrichment=enable_enrichment,
                from_date=from_date,
                to_date=to_date,
                timezone=timezone_obj,
                gemini_api_key=api_key,
                model=model,
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

    def rank(
        self,
        site_dir: str,
        comparisons: int = 1,
        export_parquet: bool = False,
        gemini_key: str | None = None,
        model: str | None = None,
        debug: bool = False,
    ):
        """
        Run ranking comparisons to build ELO scores for blog posts.

        Uses a three-turn conversation protocol:
        1. Agent chooses winner between two posts
        2. Agent comments on Post A (with existing comments as context)
        3. Agent comments on Post B (with existing comments as context)

        Each comparison randomly selects a profile to impersonate, creating
        diverse perspectives on post quality.

        Rankings are stored in DuckDB for fast updates and queries. Optionally
        export to Parquet for sharing/external analytics.

        Args:
            site_dir: Root directory of MkDocs site (contains posts/ and profiles/)
            comparisons: Number of comparisons to run (default: 1)
            export_parquet: Export rankings to Parquet after comparisons (default: False)
            gemini_key: Google Gemini API key
            model: Gemini model to use (default: models/gemini-flash-latest, configurable in mkdocs.yml)
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

        site_path = Path(site_dir).resolve()
        posts_dir = site_path / "posts"
        profiles_dir = site_path / "profiles"
        rankings_dir = site_path / "rankings"

        # Validate directories
        if not posts_dir.exists():
            console.print(
                Panel(
                    f"[red]Posts directory not found: {posts_dir}[/red]\n\n"
                    f"Make sure you're pointing to a valid MkDocs site root.",
                    title="Directory Not Found",
                    border_style="red",
                )
            )
            return

        if not profiles_dir.exists():
            console.print(
                Panel(
                    f"[red]Profiles directory not found: {profiles_dir}[/red]\n\n"
                    f"Make sure you've processed at least one WhatsApp export first.",
                    title="Directory Not Found",
                    border_style="red",
                )
            )
            return

        # Get list of profiles
        profile_files = list(profiles_dir.glob("*.md"))
        if not profile_files:
            console.print(
                Panel(
                    f"[red]No profiles found in {profiles_dir}[/red]\n\n"
                    f"Process a WhatsApp export first to create author profiles.",
                    title="No Profiles",
                    border_style="red",
                )
            )
            return

        # Initialize ratings if needed
        try:
            store = initialize_ratings(posts_dir, rankings_dir)
            console.print(f"[dim]Using rankings database: {store.db_path}[/dim]\n")
        except ValueError as e:
            console.print(
                Panel(
                    f"[red]{str(e)}[/red]",
                    title="Initialization Failed",
                    border_style="red",
                )
            )
            return

        # Run comparisons
        api_key = os.getenv("GOOGLE_API_KEY")

        # Load site config and create model config for ranking
        site_config = load_site_config(site_path)
        model_config = ModelConfig(cli_model=model, site_config=site_config)
        ranking_model = model_config.get_model("ranking")

        for i in range(comparisons):
            console.print(
                Panel(
                    f"[bold cyan]Comparison {i + 1} of {comparisons}[/bold cyan]",
                    border_style="cyan",
                )
            )

            try:
                # Select posts to compare (prioritize posts with fewest games)
                post_a_id, post_b_id = get_posts_to_compare(rankings_dir)
                console.print("\n[bold]Comparing:[/bold]")
                console.print(f"  Post A: [cyan]{post_a_id}[/cyan]")
                console.print(f"  Post B: [cyan]{post_b_id}[/cyan]")

                # Randomly select a profile to impersonate
                profile_path = random.choice(profile_files)
                console.print(f"  Judge: [magenta]{profile_path.stem[:8]}...[/magenta]\n")

                # Run three-turn comparison
                result = run_comparison(
                    site_dir=site_path,
                    post_a_id=post_a_id,
                    post_b_id=post_b_id,
                    profile_path=profile_path,
                    api_key=api_key,
                    model=ranking_model,
                )

                # Update ELO ratings
                new_rating_a, new_rating_b = update_ratings(
                    rankings_dir=rankings_dir,
                    post_a=post_a_id,
                    post_b=post_b_id,
                    winner=result["winner"],
                )

                console.print(
                    Panel(
                        f"[green]✓ Comparison complete![/green]\n\n"
                        f"Winner: Post {result['winner']}\n\n"
                        f"[bold]Updated ELO ratings:[/bold]\n"
                        f"  Post A: [cyan]{new_rating_a:.0f}[/cyan]\n"
                        f"  Post B: [cyan]{new_rating_b:.0f}[/cyan]",
                        border_style="green",
                    )
                )

                # Show some space between comparisons
                if i < comparisons - 1:
                    console.print("\n")

            except Exception as e:
                console.print(
                    Panel(
                        f"[red]Error during comparison: {str(e)}[/red]",
                        title="Comparison Failed",
                        border_style="red",
                    )
                )
                if logger.level == logging.DEBUG:
                    raise
                continue

        # Export to Parquet if requested
        if export_parquet:
            console.print("\n[cyan]Exporting rankings to Parquet...[/cyan]")
            store.export_to_parquet()
            console.print("[green]✓ Exported to Parquet[/green]")

        # Show summary
        console.print("\n")

        summary_text = (
            f"[bold green]✓ Ranking session complete![/bold green]\n\n"
            f"Comparisons completed: {comparisons}\n"
            f"Rankings stored in: {rankings_dir}\n\n"
            f"[bold]Primary storage:[/bold]\n"
            f"• rankings.duckdb - DuckDB database (fast updates/queries)"
        )

        if export_parquet:
            summary_text += (
                "\n\n[bold]Parquet exports:[/bold]\n"
                "• elo_ratings.parquet - Current ELO scores\n"
                "• elo_history.parquet - Full comparison history"
            )
        else:
            summary_text += "\n\n[dim]Tip: Use --export_parquet to create Parquet files for sharing/analytics[/dim]"

        console.print(
            Panel(
                summary_text,
                title="Session Complete",
                border_style="green",
            )
        )

    def edit_post(
        self,
        post_path: str,
        site_dir: str | None = None,
        model: str | None = None,
    ):
        """
        Run editor agent on a blog post using LLM with RAG and meta-LLM tools.

        The editor can:
        - Query RAG for related past posts
        - Ask a separate LLM for ideas/facts/metaphors
        - Make targeted edits or full rewrites
        - Publish immediately if post is already good

        Args:
            post_path: Path to the post markdown file
            site_dir: Site directory (for finding RAG database). If not provided, uses post_path parent.
            model: Gemini model to use (default: models/gemini-flash-latest, configurable in mkdocs.yml)
        """
        post_file = Path(post_path).resolve()
        if not post_file.exists():
            console.print(f"[red]Post not found: {post_file}[/red]")
            return

        # Determine site directory
        if site_dir:
            site_path = Path(site_dir).resolve()
        else:
            # Assume post is in docs/posts/ -> site root is docs/..
            site_path = post_file.parent.parent

        # Load configuration
        site_config = load_site_config(site_path / "docs")
        model_config = ModelConfig(cli_model=model, site_config=site_config)

        # Get API key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            console.print("[red]Error: GEMINI_API_KEY environment variable not set[/red]")
            return

        console.print(
            Panel(
                f"[bold]Editing Post with LLM Agent[/bold]\n\n"
                f"Post: {post_file.name}\n"
                f"Model: {model_config.get_model('editor')}\n"
                f"RAG: {site_path / 'docs' / 'rag'}\n",
                title="Editor Session",
                border_style="cyan",
            )
        )

        async def _run():
            client = genai.Client(api_key=api_key)
            try:
                result = await run_editor_session(
                    post_path=post_file,
                    client=client,
                    model_config=model_config,
                    rag_dir=site_path / "docs" / "rag",
                    context={},
                )

                # Save edited post
                post_file.write_text(result.final_content, encoding="utf-8")

                # Display results
                status_color = "green" if result.decision == "publish" else "yellow"
                console.print(
                    Panel(
                        f"[bold {status_color}]Decision: {result.decision.upper()}[/bold {status_color}]\n\n"
                        f"Edits made: {'Yes' if result.edits_made else 'No'}\n"
                        f"Tool calls: {len(result.tool_calls)}\n"
                        f"Notes: {result.notes}\n\n"
                        f"Post saved: {post_file}",
                        title="Editor Complete",
                        border_style=status_color,
                    )
                )

                # Show tool call log
                if result.tool_calls:
                    console.print("\n[bold]Tool Calls:[/bold]")
                    for i, call in enumerate(result.tool_calls, 1):
                        console.print(f"  {i}. {call['tool']}({list(call['args'].keys())})")

            finally:
                client.close()

        asyncio.run(_run())


def main():
    fire.Fire(EgregoraCLI)


if __name__ == "__main__":
    main()
