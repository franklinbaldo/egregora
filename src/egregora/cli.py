"""Typer-based CLI for Egregora v2."""

import asyncio
import importlib
import logging
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from google import genai
from rich.markup import escape
from rich.panel import Panel

from .config import ProcessConfig, RankingCliConfig
from .editor_agent import run_editor_session
from .logging_setup import configure_logging, console
from .config import ModelConfig, load_site_config
from .pipeline import process_whatsapp_export
from .config import find_mkdocs_file, resolve_site_paths
from .site_scaffolding import ensure_mkdocs_project

app = typer.Typer(
    name="egregora",
    help="Ultra-simple WhatsApp to blog pipeline with LLM-powered content generation",
    add_completion=False,
)
logger = logging.getLogger(__name__)

@app.callback()
def _initialize_cli() -> None:
    """Configure logging when the CLI is invoked."""

    configure_logging()


def _resolve_gemini_key(cli_override: str | None) -> str | None:
    """Return the Gemini API key honoring CLI override precedence."""

    return cli_override or os.getenv("GOOGLE_API_KEY")


@app.command()
def init(
    output_dir: Annotated[
        Path,
        typer.Argument(help="Directory path for the new site (e.g., 'my-blog')"),
    ],
):
    """
    Initialize a new MkDocs site scaffold for serving Egregora posts.

    Creates:
    - mkdocs.yml with Material theme + blog plugin
    - Directory structure (docs/, posts/, profiles/, media/)
    - README.md with quick start instructions
    - .gitignore for Python and MkDocs
    - Starter pages (homepage, about, profiles index)
    """
    site_root = output_dir.resolve()
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
                f"• Process WhatsApp export: [cyan]egregora process export.zip --output={output_dir}[/cyan]",
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


def _validate_and_run_process(config: ProcessConfig):  # noqa: PLR0912, PLR0915
    """Validate process configuration and run the pipeline."""
    if config.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate timezone
    timezone_obj = None
    if config.timezone:
        try:
            timezone_obj = ZoneInfo(config.timezone)
            console.print(f"[green]Using timezone: {config.timezone}[/green]")
        except Exception as e:
            console.print(f"[red]Invalid timezone '{config.timezone}': {e}[/red]")
            raise typer.Exit(1) from e

    retrieval_mode = (config.retrieval_mode or "ann").lower()
    if retrieval_mode not in {"ann", "exact"}:
        console.print("[red]Invalid retrieval mode. Choose 'ann' or 'exact'.[/red]")
        raise typer.Exit(1)

    if retrieval_mode == "exact" and config.retrieval_nprobe:
        console.print(
            "[yellow]Ignoring retrieval_nprobe: only applicable to ANN search.[/yellow]"
        )
        config.retrieval_nprobe = None

    if config.retrieval_nprobe is not None and config.retrieval_nprobe <= 0:
        console.print("[red]retrieval_nprobe must be positive when provided.[/red]")
        raise typer.Exit(1)

    if config.retrieval_overfetch is not None and config.retrieval_overfetch <= 0:
        console.print("[red]retrieval_overfetch must be positive when provided.[/red]")
        raise typer.Exit(1)

    config.retrieval_mode = retrieval_mode

    # Parse dates
    from_date_obj = config.from_date
    to_date_obj = config.to_date

    # Ensure output directory has MkDocs scaffold
    output_dir = config.output_dir.expanduser().resolve()
    config.output_dir = output_dir
    mkdocs_path = find_mkdocs_file(output_dir)
    if not mkdocs_path:
        output_dir.mkdir(parents=True, exist_ok=True)
        warning_message = (
            "[yellow]Warning:[/yellow] MkDocs configuration not found in "
            f"{output_dir}. Egregora can initialize a new scaffold before processing."
        )
        console.print(warning_message)

        proceed = True
        if any(output_dir.iterdir()):
            proceed = typer.confirm(
                "The output directory is not empty and lacks mkdocs.yml. "
                "Initialize a fresh MkDocs scaffold here?",
                default=False,
            )

        if not proceed:
            console.print("[red]Aborting processing at user's request.[/red]")
            raise typer.Exit(1)

        logger.info("Initializing MkDocs scaffold in %s", output_dir)
        ensure_mkdocs_project(output_dir)
        console.print("[green]Initialized MkDocs scaffold. Continuing with processing.[/green]")

    # Get API key
    api_key = _resolve_gemini_key(config.gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)

    # Run pipeline
    try:
        console.print(
            Panel(
                f"[cyan]Processing:[/cyan] {config.zip_file}\n"
                f"[cyan]Output:[/cyan] {output_dir}\n"
                f"[cyan]Grouping:[/cyan] {config.period}",
                title="⚙️  Egregora Pipeline",
                border_style="cyan",
            )
        )
        process_whatsapp_export(
            zip_path=config.zip_file,
            output_dir=config.output_dir,
            gemini_api_key=api_key,
            period=config.period,
            enable_enrichment=config.enable_enrichment,
            from_date=from_date_obj,
            to_date=to_date_obj,
            timezone=timezone_obj,
            model=config.model,
            retrieval_mode=config.retrieval_mode,
            retrieval_nprobe=config.retrieval_nprobe,
            retrieval_overfetch=config.retrieval_overfetch,
        )
        console.print("[green]Processing completed successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Pipeline failed: {e}[/red]")
        if config.debug:
            raise
        raise typer.Exit(1) from e


@app.command()
def process(  # noqa: PLR0913
    zip_file: Annotated[Path, typer.Argument(help="Path to WhatsApp export ZIP")],
    output: Annotated[Path, typer.Option(help="Output directory for generated site")] = Path(
        "output"
    ),
    period: Annotated[str, typer.Option(help="Grouping period: 'day' or 'week'")] = "day",
    enable_enrichment: Annotated[
        bool, typer.Option(help="Enable LLM enrichment for URLs/media")
    ] = True,
    from_date: Annotated[
        str | None, typer.Option(help="Only process messages from this date onwards (YYYY-MM-DD)")
    ] = None,
    to_date: Annotated[
        str | None, typer.Option(help="Only process messages up to this date (YYYY-MM-DD)")
    ] = None,
    timezone: Annotated[
        str | None, typer.Option(help="Timezone for date parsing (e.g., 'America/New_York')")
    ] = None,
    gemini_key: Annotated[
        str | None,
        typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)"),
    ] = None,
    model: Annotated[
        str | None, typer.Option(help="Gemini model to use (or configure in mkdocs.yml)")
    ] = None,
    retrieval_mode: Annotated[
        str,
        typer.Option(
            help="Retrieval strategy: 'ann' (default) or 'exact'",
            case_sensitive=False,
        ),
    ] = "ann",
    retrieval_nprobe: Annotated[
        int | None,
        typer.Option(help="Advanced: override DuckDB VSS nprobe for ANN retrieval"),
    ] = None,
    retrieval_overfetch: Annotated[
        int | None,
        typer.Option(help="Advanced: multiply ANN candidate pool before filtering"),
    ] = None,
    debug: Annotated[bool, typer.Option(help="Enable debug logging")] = False,
):
    """
    Process WhatsApp export and generate blog posts + author profiles.

    The LLM decides:
    - What's worth writing about (filters noise automatically)
    - How many posts per period (0-N)
    - All metadata (title, slug, tags, summary, etc)
    - Which author profiles to update based on contributions
    """
    # Parse dates first
    from_date_obj = None
    to_date_obj = None
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        except ValueError as e:
            console.print(f"[red]Invalid from_date format: {e}[/red]")
            console.print("[yellow]Expected format: YYYY-MM-DD[/yellow]")
            raise typer.Exit(1) from e

    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
        except ValueError as e:
            console.print(f"[red]Invalid to_date format: {e}[/red]")
            console.print("[yellow]Expected format: YYYY-MM-DD[/yellow]")
            raise typer.Exit(1) from e

    config = ProcessConfig(
        zip_file=zip_file,
        output_dir=output,
        period=period,
        enable_enrichment=enable_enrichment,
        from_date=from_date_obj,
        to_date=to_date_obj,
        timezone=timezone,
        gemini_key=gemini_key,
        model=model,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        debug=debug,
    )

    _validate_and_run_process(config)


@app.command()
def edit(
    post_path: Annotated[Path, typer.Argument(help="Path to the post markdown file")],
    site_dir: Annotated[
        Path | None,
        typer.Option(help="Site directory (for finding RAG database). Defaults to post parent."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(help="Gemini model to use (default: models/gemini-flash-latest)"),
    ] = None,
    gemini_key: Annotated[
        str | None,
        typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)"),
    ] = None,
):
    """
    Interactive LLM-powered editor with RAG and meta-LLM capabilities.

    The editor can:
    - Read and edit posts line-by-line
    - Search similar posts via RAG
    - Make autonomous editing decisions
    """
    post_file = post_path.resolve()
    if not post_file.exists():
        console.print(f"[red]Post not found: {post_file}[/red]")
        raise typer.Exit(1)

    # Determine site directory
    if site_dir:
        site_path = site_dir.resolve()
    else:
        # Assume post is in site/posts/**/*.md
        site_path = post_file.parent
        while site_path.name == "posts" or site_path.parent.name == "posts":
            site_path = site_path.parent
            if site_path == site_path.parent:  # Reached root
                site_path = Path.cwd()
                break

    console.print(f"[cyan]Site directory: {site_path}[/cyan]")

    rag_dir = site_path / "rag"
    if not rag_dir.exists():
        console.print("[yellow]RAG directory not found. Editor will work without RAG.[/yellow]")

    # Get API key
    api_key = _resolve_gemini_key(gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)

    # Load model config
    site_config = load_site_config(site_path)
    model_config = ModelConfig(cli_model=model, site_config=site_config)

    # Create client
    client = genai.Client(api_key=api_key)

    # Run editor session
    try:
        result = asyncio.run(
            run_editor_session(
                post_path=post_file,
                client=client,
                model_config=model_config,
                rag_dir=rag_dir,
            )
        )

        # Persist edited content to disk
        if result.edits_made:
            post_file.write_text(result.final_content, encoding="utf-8")
            console.print(f"[green]Saved edited content to {post_file}[/green]")

        console.print(
            Panel(
                f"[bold]Editor Session Complete[/bold]\n\n"
                f"Decision: {result.decision}\n"
                f"Notes: {result.notes}\n"
                f"Edits made: {result.edits_made}\n"
                f"Tool calls: {len(result.tool_calls)}",
                title="✅ Done",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Editor session failed: {e}[/red]")
        raise typer.Exit(1) from e


def _register_ranking_cli(app: typer.Typer) -> None:  # noqa: PLR0915
    """Register ranking commands when the optional extra is installed."""

    try:
        ranking_agent = importlib.import_module("egregora.ranking.agent")
        ranking_elo = importlib.import_module("egregora.ranking.elo")
        ranking_store_module = importlib.import_module("egregora.ranking.store")
        run_comparison = ranking_agent.run_comparison
        get_posts_to_compare = ranking_elo.get_posts_to_compare
        RankingStore = ranking_store_module.RankingStore
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on installation
        missing = exc.name or "egregora.ranking"

        @app.command(hidden=True)
        def rank(  # noqa: PLR0913
            site_dir: Annotated[Path, typer.Argument(help="Path to MkDocs site directory")],
            comparisons: Annotated[
                int, typer.Option(help="Number of comparisons to run")
            ] = 1,
            strategy: Annotated[
                str, typer.Option(help="Post selection strategy")
            ] = "fewest_games",
            export_parquet: Annotated[
                bool, typer.Option(help="Export rankings to Parquet after comparisons")
            ] = False,
            gemini_key: Annotated[
                str | None,
                typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)"),
            ] = None,
            model: Annotated[
                str | None,
                typer.Option(help="Gemini model to use (or configure in mkdocs.yml)"),
            ] = None,
            debug: Annotated[bool, typer.Option(help="Enable debug logging")] = False,
        ) -> None:
            install_cmd = escape("pip install 'egregora[ranking]'")
            console.print(
                f"[red]Ranking commands require the optional extra: {install_cmd}[/red]"
            )
            console.print(f"[yellow]Missing dependency: {escape(missing)}[/yellow]")
            raise typer.Exit(1)

        logger.debug("Ranking extra unavailable: %s", missing)
        return

    def _run_ranking_session(  # noqa: PLR0915
        config: RankingCliConfig, gemini_key: str | None
    ) -> None:
        if config.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        site_path = config.site_dir.resolve()
        if not site_path.exists():
            console.print(f"[red]Site directory not found: {site_path}[/red]")
            raise typer.Exit(1)

        site_paths = resolve_site_paths(site_path)
        posts_dir = site_paths.posts_dir
        rankings_dir = site_paths.rankings_dir
        profiles_dir = site_paths.profiles_dir

        if not posts_dir.exists():
            console.print(f"[red]Posts directory not found: {posts_dir}[/red]")
            console.print("Run 'egregora process' first to generate posts")
            raise typer.Exit(1)

        store = RankingStore(rankings_dir)
        post_files = sorted(posts_dir.glob("**/*.md"))
        post_ids = [p.stem for p in post_files]

        if not post_ids:
            console.print("[red]No posts found to rank[/red]")
            raise typer.Exit(1)

        newly_initialized = store.initialize_ratings(post_ids)
        if newly_initialized > 0:
            console.print(f"[green]Initialized {newly_initialized} new posts with ELO 1500[/green]")

        api_key = _resolve_gemini_key(gemini_key)
        if not api_key:
            console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
            console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
            raise typer.Exit(1)

        site_config = load_site_config(site_path)
        model_config = ModelConfig(cli_model=config.model, site_config=site_config)
        ranking_model = model_config.get_model("ranking")
        logger.info("[blue]⚖️  Ranking model:[/] %s", ranking_model)

        for i in range(config.comparisons):
            console.print(
                Panel(
                    f"[bold cyan]Comparison {i + 1} of {config.comparisons}[/bold cyan]",
                    border_style="cyan",
                )
            )

            try:
                post_a_id, post_b_id = get_posts_to_compare(
                    rankings_dir, strategy=config.strategy
                )
                console.print(f"[cyan]Comparing: {post_a_id} vs {post_b_id}[/cyan]")
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                break

            profile_files = list(profiles_dir.glob("*.md"))
            if not profile_files:
                console.print("[yellow]No profiles found, using default judge[/yellow]")
                default_profile = profiles_dir / "judge.md"
                default_profile.parent.mkdir(parents=True, exist_ok=True)
                default_profile.write_text(
                    "---\nuuid: judge\nalias: Judge\n---\nA fair and balanced judge."
                )
                profile_files = [default_profile]

            profile_path = random.choice(profile_files)

            try:
                run_comparison(
                    site_dir=site_path,
                    post_a_id=post_a_id,
                    post_b_id=post_b_id,
                    profile_path=profile_path,
                    api_key=api_key,
                    model=ranking_model,
                )
            except Exception as e:
                console.print(f"[red]Comparison failed: {e}[/red]")
                if config.debug:
                    raise
                continue

        if config.export_parquet:
            store.export_to_parquet()
            console.print(f"[green]Exported rankings to {rankings_dir}[/green]")

        stats = store.stats()
        console.print(
            Panel(
                f"[bold]Ranking Statistics:[/bold]\n"
                f"• Total posts: {stats['total_posts']}\n"
                f"• Total comparisons: {stats['total_comparisons']}\n"
                f"• Avg games per post: {stats['avg_games_per_post']:.1f}\n"
                f"• Highest ELO: {stats['highest_elo']:.0f}\n"
                f"• Lowest ELO: {stats['lowest_elo']:.0f}",
                title="📊 Rankings",
                border_style="green",
            )
        )

    @app.command()
    def rank(  # noqa: PLR0913
        site_dir: Annotated[Path, typer.Argument(help="Path to MkDocs site directory")],
        comparisons: Annotated[
            int, typer.Option(help="Number of comparisons to run")
        ] = 1,
        strategy: Annotated[
            str, typer.Option(help="Post selection strategy")
        ] = "fewest_games",
        export_parquet: Annotated[
            bool, typer.Option(help="Export rankings to Parquet after comparisons")
        ] = False,
        gemini_key: Annotated[
            str | None,
            typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)"),
        ] = None,
        model: Annotated[
            str | None, typer.Option(help="Gemini model to use (or configure in mkdocs.yml)")
        ] = None,
        debug: Annotated[bool, typer.Option(help="Enable debug logging")] = False,
    ) -> None:
        """Run ELO-based ranking comparisons on posts using the ranking agent."""

        config = RankingCliConfig(
            site_dir=site_dir,
            comparisons=comparisons,
            strategy=strategy,
            export_parquet=export_parquet,
            model=model,
            debug=debug,
        )

        _run_ranking_session(config, gemini_key)


_register_ranking_cli(app)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
