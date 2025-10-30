"""Typer-based CLI for Egregora v2."""

import asyncio
import importlib
import logging
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import typer
from google import genai
from rich.markup import escape
from rich.panel import Panel

from ..config import (
    ModelConfig,
    ProcessConfig,
    RankingCliConfig,
    find_mkdocs_file,
    load_site_config,
    resolve_site_paths,
)
from ..generation.editor import run_editor_session
from ..publication.site import ensure_mkdocs_project
from .logging_setup import configure_logging, console
from .pipeline import process_whatsapp_export

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


@app.command()
def parse(
    zip_file: Annotated[Path, typer.Argument(help="Path to WhatsApp export ZIP")],
    output: Annotated[Path, typer.Option(help="Output CSV file path")] = Path("messages.csv"),
    timezone: Annotated[
        str | None, typer.Option(help="Timezone for date parsing (e.g., 'America/New_York')")
    ] = None,
):
    """
    Parse WhatsApp export ZIP to CSV.

    This is the first stage of the pipeline. It:
    - Extracts messages from the ZIP file
    - Parses dates, times, and authors
    - Anonymizes author names to UUID5 pseudonyms
    - Saves structured data to CSV

    Output CSV contains: timestamp, date, time, author, message, group_slug, group_name
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    import duckdb
    import ibis

    from ..core.models import WhatsAppExport
    from ..ingestion.parser import parse_export
    from .pipeline import discover_chat_file
    from .serialization import save_table_to_csv

    # Validate inputs
    zip_path = zip_file.resolve()
    if not zip_path.exists():
        console.print(f"[red]ZIP file not found: {zip_path}[/red]")
        raise typer.Exit(1)

    output_path = output.resolve()

    # Parse timezone
    timezone_obj = None
    if timezone:
        try:
            timezone_obj = ZoneInfo(timezone)
            console.print(f"[green]Using timezone: {timezone}[/green]")
        except Exception as e:
            console.print(f"[red]Invalid timezone '{timezone}': {e}[/red]")
            raise typer.Exit(1) from e

    # Setup DuckDB backend
    connection = duckdb.connect(":memory:")
    backend = ibis.duckdb.from_connection(connection)
    old_backend = getattr(ibis.options, "default_backend", None)

    try:
        ibis.options.default_backend = backend

        console.print(f"[cyan]Parsing:[/cyan] {zip_path}")

        # Discover chat file
        group_name, chat_file = discover_chat_file(zip_path)
        from ..core.types import GroupSlug

        group_slug = GroupSlug(group_name.lower().replace(" ", "-"))
        console.print(f"[yellow]Group:[/yellow] {group_name}")

        # Create export object
        export = WhatsAppExport(
            zip_path=zip_path,
            group_name=group_name,
            group_slug=group_slug,
            export_date=datetime.now().date(),
            chat_file=chat_file,
            media_files=[],
        )

        # Parse messages
        messages_table = parse_export(export, timezone=timezone_obj)
        total_messages = messages_table.count().execute()

        console.print(f"[green]✅ Parsed {total_messages} messages[/green]")

        # Save to CSV
        save_table_to_csv(messages_table, output_path)
        console.print(f"[green]💾 Saved to {output_path}[/green]")

    finally:
        ibis.options.default_backend = old_backend
        connection.close()


@app.command()
def group(
    input_csv: Annotated[Path, typer.Argument(help="Input CSV file from parse stage")],
    period: Annotated[str, typer.Option(help="Grouping period: 'day', 'week', or 'month'")] = "day",
    output_dir: Annotated[Path, typer.Option(help="Output directory for period CSV files")] = Path(
        "periods"
    ),
    from_date: Annotated[
        str | None, typer.Option(help="Only include messages from this date onwards (YYYY-MM-DD)")
    ] = None,
    to_date: Annotated[
        str | None, typer.Option(help="Only include messages up to this date (YYYY-MM-DD)")
    ] = None,
):
    """
    Group messages by time period (day/week/month).

    This is the second stage of the pipeline. It:
    - Loads messages from CSV
    - Optionally filters by date range
    - Groups messages by the specified period
    - Saves each period to a separate CSV file

    Output files are named: {period_key}.csv (e.g., 2025-01-15.csv, 2025-W03.csv)
    """
    from datetime import datetime

    import duckdb
    import ibis

    from .pipeline import group_by_period
    from .serialization import load_table_from_csv, save_table_to_csv

    # Validate inputs
    input_path = input_csv.resolve()
    if not input_path.exists():
        console.print(f"[red]Input CSV not found: {input_path}[/red]")
        raise typer.Exit(1)

    if period not in {"day", "week", "month"}:
        console.print(f"[red]Invalid period '{period}'. Choose: day, week, or month[/red]")
        raise typer.Exit(1)

    output_path = output_dir.resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # Parse dates
    from_date_obj = None
    to_date_obj = None

    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        except ValueError as e:
            console.print(f"[red]Invalid from_date format: {e}[/red]")
            raise typer.Exit(1) from e

    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
        except ValueError as e:
            console.print(f"[red]Invalid to_date format: {e}[/red]")
            raise typer.Exit(1) from e

    # Setup DuckDB backend
    connection = duckdb.connect(":memory:")
    backend = ibis.duckdb.from_connection(connection)
    old_backend = getattr(ibis.options, "default_backend", None)

    try:
        ibis.options.default_backend = backend

        console.print(f"[cyan]Loading:[/cyan] {input_path}")
        messages_table = load_table_from_csv(input_path)

        # Filter by date range if specified
        if from_date_obj or to_date_obj:
            original_count = messages_table.count().execute()

            if from_date_obj and to_date_obj:
                messages_table = messages_table.filter(
                    (messages_table.timestamp.date() >= from_date_obj)
                    & (messages_table.timestamp.date() <= to_date_obj)
                )
                console.print(f"[cyan]Filtering:[/cyan] {from_date_obj} to {to_date_obj}")
            elif from_date_obj:
                messages_table = messages_table.filter(
                    messages_table.timestamp.date() >= from_date_obj
                )
                console.print(f"[cyan]Filtering:[/cyan] from {from_date_obj}")
            elif to_date_obj:
                messages_table = messages_table.filter(messages_table.timestamp.date() <= to_date_obj)
                console.print(f"[cyan]Filtering:[/cyan] up to {to_date_obj}")

            filtered_count = messages_table.count().execute()
            removed = original_count - filtered_count
            console.print(f"[yellow]Filtered out {removed} messages (kept {filtered_count})[/yellow]")

        # Group by period
        console.print(f"[cyan]Grouping by:[/cyan] {period}")
        periods = group_by_period(messages_table, period)

        if not periods:
            console.print("[yellow]No periods found after grouping[/yellow]")
            raise typer.Exit(0)

        console.print(f"[green]Found {len(periods)} periods[/green]")

        # Save each period to CSV
        for period_key, period_table in periods.items():
            period_output = output_path / f"{period_key}.csv"
            period_count = period_table.count().execute()
            console.print(f"  [cyan]{period_key}:[/cyan] {period_count} messages → {period_output}")
            save_table_to_csv(period_table, period_output)

        console.print(f"[green]✅ Saved {len(periods)} period files to {output_path}[/green]")

    finally:
        ibis.options.default_backend = old_backend
        connection.close()


@app.command()
def enrich(  # noqa: PLR0913
    input_csv: Annotated[Path, typer.Argument(help="Input CSV file (from parse or group stage)")],
    zip_file: Annotated[Path, typer.Option(help="Original WhatsApp ZIP file (for media extraction)")],
    output: Annotated[Path, typer.Option(help="Output enriched CSV file")],
    site_dir: Annotated[Path, typer.Option(help="Site directory (for media storage)")],
    gemini_key: Annotated[
        str | None,
        typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)"),
    ] = None,
    enable_url: Annotated[bool, typer.Option(help="Enable URL enrichment")] = True,
    enable_media: Annotated[bool, typer.Option(help="Enable media enrichment")] = True,
    max_enrichments: Annotated[
        int, typer.Option(help="Maximum number of enrichments to perform")
    ] = 50,
):
    """
    Enrich messages with LLM-generated context for URLs and media.

    This is the third stage of the pipeline. It:
    - Loads messages from CSV
    - Extracts media files from the ZIP
    - Optionally enriches URLs with LLM descriptions
    - Optionally enriches media (images/videos) with LLM descriptions
    - Adds enrichment as new rows (author='egregora')
    - Saves enriched table to CSV

    Requires GOOGLE_API_KEY environment variable or --gemini-key flag.
    """
    import duckdb
    import ibis
    from google import genai

    from ..augmentation.enrichment import enrich_table, extract_and_replace_media
    from ..config import ModelConfig, load_site_config, resolve_site_paths
    from ..utils.cache import EnrichmentCache
    from ..utils.smart_client import SmartGeminiClient
    from .serialization import load_table_with_auto_schema, save_table_to_csv

    # Validate inputs
    input_path = input_csv.resolve()
    if not input_path.exists():
        console.print(f"[red]Input CSV not found: {input_path}[/red]")
        raise typer.Exit(1)

    zip_path = zip_file.resolve()
    if not zip_path.exists():
        console.print(f"[red]ZIP file not found: {zip_path}[/red]")
        raise typer.Exit(1)

    site_path = site_dir.resolve()
    if not site_path.exists():
        console.print(f"[red]Site directory not found: {site_path}[/red]")
        console.print("[yellow]Run 'egregora init <site-dir>' to create a site[/yellow]")
        raise typer.Exit(1)

    output_path = output.resolve()

    # Get API key
    api_key = _resolve_gemini_key(gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)

    # Setup paths and config
    site_paths = resolve_site_paths(site_path)
    site_config = load_site_config(site_path)
    model_config = ModelConfig(site_config=site_config)

    # Setup DuckDB backend
    connection = duckdb.connect(":memory:")
    backend = ibis.duckdb.from_connection(connection)
    old_backend = getattr(ibis.options, "default_backend", None)

    client: genai.Client | None = None
    try:
        ibis.options.default_backend = backend
        client = genai.Client(api_key=api_key)

        console.print(f"[cyan]Loading:[/cyan] {input_path}")
        messages_table = load_table_with_auto_schema(input_path)
        original_count = messages_table.count().execute()

        console.print(f"[cyan]Loaded {original_count} messages[/cyan]")

        # Extract media from ZIP
        console.print("[yellow]Extracting media from ZIP...[/yellow]")
        messages_table, media_mapping = extract_and_replace_media(
            messages_table,
            zip_path,
            site_paths.docs_dir,
            site_paths.posts_dir,
            "chat",  # generic group slug for standalone enrichment
        )

        console.print(f"[green]Extracted {len(media_mapping)} media files[/green]")

        # Setup smart clients and cache
        text_batch_client = SmartGeminiClient(client, model_config.get_model("enricher"))
        vision_batch_client = SmartGeminiClient(client, model_config.get_model("enricher_vision"))

        cache_dir = Path(".egregora-cache") / site_paths.site_root.name
        enrichment_cache = EnrichmentCache(cache_dir)

        console.print(
            f"[cyan]Enriching with:[/cyan] URLs={enable_url}, Media={enable_media}, Max={max_enrichments}"
        )

        # Enrich table
        enriched_table = enrich_table(
            messages_table,
            media_mapping,
            text_batch_client,
            vision_batch_client,
            enrichment_cache,
            site_paths.docs_dir,
            site_paths.posts_dir,
            model_config,
            enable_url=enable_url,
            enable_media=enable_media,
            max_enrichments=max_enrichments,
        )

        enriched_count = enriched_table.count().execute()
        added_rows = enriched_count - original_count

        console.print(f"[green]✅ Added {added_rows} enrichment rows[/green]")

        # Save enriched table
        save_table_to_csv(enriched_table, output_path)
        console.print(f"[green]💾 Saved to {output_path}[/green]")

    finally:
        try:
            if "enrichment_cache" in locals():
                enrichment_cache.close()
        finally:
            if client:
                client.close()
            ibis.options.default_backend = old_backend
            connection.close()


@app.command()
def gather_context(  # noqa: PLR0913
    input_csv: Annotated[Path, typer.Argument(help="Input enriched CSV file")],
    period_key: Annotated[str, typer.Option(help="Period identifier (e.g., 2025-W03)")],
    site_dir: Annotated[Path, typer.Option(help="Site directory")],
    output: Annotated[Path, typer.Option(help="Output context JSON file")],
    gemini_key: Annotated[
        str | None,
        typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)"),
    ] = None,
    enable_rag: Annotated[bool, typer.Option(help="Enable RAG retrieval")] = True,
    retrieval_mode: Annotated[
        str, typer.Option(help="Retrieval strategy: 'ann' or 'exact'")
    ] = "ann",
    retrieval_nprobe: Annotated[
        int | None, typer.Option(help="DuckDB VSS nprobe for ANN")
    ] = None,
    retrieval_overfetch: Annotated[
        int | None, typer.Option(help="Multiply ANN candidate pool")
    ] = None,
):
    """
    Gather context for post generation (RAG, profiles, freeform memory).

    This is the fourth stage of the pipeline. It:
    - Loads enriched messages from CSV
    - Formats conversation as markdown table
    - Queries RAG for similar posts (if enabled)
    - Loads author profiles
    - Loads freeform memory from previous period
    - Loads site configuration
    - Saves all context to JSON file

    The JSON output can be inspected and reused for multiple generation runs.
    """
    import json

    import duckdb
    import ibis
    from google import genai

    from ..augmentation.profiler import get_active_authors
    from ..config import ModelConfig, load_mkdocs_config, load_site_config, resolve_site_paths
    from ..generation.writer.context import _load_profiles_context, _query_rag_for_context
    from ..generation.writer.formatting import _build_conversation_markdown, _load_freeform_memory
    from ..utils.smart_client import SmartGeminiClient
    from .serialization import load_table_with_auto_schema

    # Validate inputs
    input_path = input_csv.resolve()
    if not input_path.exists():
        console.print(f"[red]Input CSV not found: {input_path}[/red]")
        raise typer.Exit(1)

    site_path = site_dir.resolve()
    if not site_path.exists():
        console.print(f"[red]Site directory not found: {site_path}[/red]")
        raise typer.Exit(1)

    output_path = output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Setup paths and config
    site_paths = resolve_site_paths(site_path)
    site_config = load_site_config(site_path)
    model_config = ModelConfig(site_config=site_config)
    mkdocs_config = load_mkdocs_config(site_path)

    # Setup DuckDB backend
    connection = duckdb.connect(":memory:")
    backend = ibis.duckdb.from_connection(connection)
    old_backend = getattr(ibis.options, "default_backend", None)

    client: genai.Client | None = None
    try:
        ibis.options.default_backend = backend

        console.print(f"[cyan]Loading:[/cyan] {input_path}")
        enriched_table = load_table_with_auto_schema(input_path)
        message_count = enriched_table.count().execute()
        console.print(f"[cyan]Loaded {message_count} messages[/cyan]")

        # Build conversation markdown
        console.print("[yellow]Formatting conversation...[/yellow]")
        conversation_md = _build_conversation_markdown(enriched_table)

        # Get active authors
        active_authors = get_active_authors(enriched_table)
        console.print(f"[cyan]Active authors: {len(active_authors)}[/cyan]")

        # Load profiles
        console.print("[yellow]Loading profiles...[/yellow]")
        profiles = _load_profiles_context(active_authors, site_paths.profiles_dir)

        # Load freeform memory
        console.print("[yellow]Loading freeform memory...[/yellow]")
        freeform_memory = _load_freeform_memory(site_paths.posts_dir)

        # RAG context (if enabled)
        rag_similar_posts: list[dict[str, Any]] = []
        rag_context_markdown = ""
        if enable_rag:
            api_key = _resolve_gemini_key(gemini_key)
            if not api_key:
                console.print("[yellow]Warning: RAG enabled but no API key provided, skipping RAG[/yellow]")
            else:
                console.print("[yellow]Querying RAG for similar posts...[/yellow]")
                client = genai.Client(api_key=api_key)
                embedding_batch_client = SmartGeminiClient(
                    client, model_config.get_model("embedding")
                )

                rag_context_markdown, rag_similar_posts = _query_rag_for_context(
                    enriched_table,
                    embedding_batch_client,
                    site_paths.rag_dir,
                    embedding_model=model_config.get_model("embedding"),
                    embedding_output_dimensionality=model_config.embedding_output_dimensionality,
                    retrieval_mode=retrieval_mode,
                    retrieval_nprobe=retrieval_nprobe,
                    retrieval_overfetch=retrieval_overfetch,
                    return_records=True,
                )
                console.print(f"[green]Found {len(rag_similar_posts)} similar posts[/green]")

        # Build context structure
        context = {
            "period_key": period_key,
            "conversation_markdown": conversation_md,
            "active_authors": list(active_authors),
            "profiles": profiles,
            "freeform_memory": freeform_memory,
            "rag_similar_posts": rag_similar_posts,
            "rag_context_markdown": rag_context_markdown,
            "site_config": {
                "markdown_extensions": mkdocs_config.get("markdown_extensions", []),
                "custom_writer_prompt": site_config.get("custom_writer_prompt"),
            },
            "message_count": message_count,
        }

        # Save to JSON
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(context, f, indent=2, ensure_ascii=False)

        console.print(f"[green]✅ Saved context to {output_path}[/green]")
        console.print("[cyan]Context includes:[/cyan]")
        console.print(f"  • {message_count} messages")
        console.print(f"  • {len(active_authors)} active authors")
        console.print(f"  • {len(rag_similar_posts)} RAG results")
        console.print(f"  • Freeform memory: {'Yes' if freeform_memory else 'No'}")

    finally:
        if client:
            client.close()
        ibis.options.default_backend = old_backend
        connection.close()


@app.command()
def write_posts(  # noqa: PLR0913
    input_csv: Annotated[Path, typer.Argument(help="Input enriched CSV file")],
    period_key: Annotated[str, typer.Option(help="Period identifier (e.g., 2025-W03)")],
    site_dir: Annotated[Path, typer.Option(help="Site directory")],
    context: Annotated[
        Path | None, typer.Option(help="Context JSON file (from gather-context command)")
    ] = None,
    gemini_key: Annotated[
        str | None,
        typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)"),
    ] = None,
    model: Annotated[
        str | None, typer.Option(help="Gemini model to use (overrides mkdocs.yml)")
    ] = None,
):
    """
    Generate blog posts from enriched messages using LLM.

    This is the fifth (final) stage of the pipeline. It:
    - Loads enriched messages from CSV
    - Loads context from JSON (if provided) or gathers inline
    - Invokes LLM with write_post tool for editorial control
    - LLM decides: what to write, how many posts, all metadata
    - Saves posts to site-dir/docs/posts/
    - Updates profiles in site-dir/docs/profiles/

    The LLM has full editorial control via function calling.
    """
    import json

    import duckdb
    import ibis
    from google import genai

    from ..config import ModelConfig, load_site_config, resolve_site_paths
    from ..generation.writer import write_posts_for_period
    from ..utils.smart_client import SmartGeminiClient
    from .serialization import load_table_with_auto_schema

    # Validate inputs
    input_path = input_csv.resolve()
    if not input_path.exists():
        console.print(f"[red]Input CSV not found: {input_path}[/red]")
        raise typer.Exit(1)

    site_path = site_dir.resolve()
    if not site_path.exists():
        console.print(f"[red]Site directory not found: {site_path}[/red]")
        raise typer.Exit(1)

    context_path = context.resolve() if context else None
    if context_path and not context_path.exists():
        console.print(f"[red]Context file not found: {context_path}[/red]")
        raise typer.Exit(1)

    # Get API key
    api_key = _resolve_gemini_key(gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)

    # Setup paths and config
    site_paths = resolve_site_paths(site_path)
    site_config = load_site_config(site_path)
    model_config = ModelConfig(cli_model=model, site_config=site_config)

    # Setup DuckDB backend
    connection = duckdb.connect(":memory:")
    backend = ibis.duckdb.from_connection(connection)
    old_backend = getattr(ibis.options, "default_backend", None)

    client: genai.Client | None = None
    try:
        ibis.options.default_backend = backend
        client = genai.Client(api_key=api_key)

        console.print(f"[cyan]Loading:[/cyan] {input_path}")
        enriched_table = load_table_with_auto_schema(input_path)
        message_count = enriched_table.count().execute()
        console.print(f"[cyan]Loaded {message_count} messages[/cyan]")

        # Load or note context source
        if context_path:
            console.print(f"[cyan]Using context from:[/cyan] {context_path}")
            with context_path.open("r", encoding="utf-8") as f:
                context_data = json.load(f)
            console.print(f"[yellow]Context includes {len(context_data.get('rag_similar_posts', []))} RAG results[/yellow]")
        else:
            console.print("[yellow]No context file provided, will gather context inline[/yellow]")

        # Setup embedding client for RAG
        embedding_batch_client = SmartGeminiClient(
            client, model_config.get_model("embedding")
        )
        embedding_dimensionality = model_config.embedding_output_dimensionality

        console.print(f"[cyan]Writer model:[/cyan] {model_config.get_model('writer')}")
        console.print(f"[yellow]Invoking LLM writer for period {period_key}...[/yellow]")

        # Write posts (this uses the existing write_posts_for_period function)
        result = write_posts_for_period(
            enriched_table,
            period_key,
            client,
            embedding_batch_client,
            site_paths.posts_dir,
            site_paths.profiles_dir,
            site_paths.rag_dir,
            model_config,
            enable_rag=True,  # RAG is handled by existing logic
            embedding_output_dimensionality=embedding_dimensionality,
            retrieval_mode="ann",  # Default, context already includes RAG results if needed
        )

        posts_count = len(result.get("posts", []))
        profiles_count = len(result.get("profiles", []))

        console.print(f"[green]✅ Generated {posts_count} posts[/green]")
        console.print(f"[green]✅ Updated {profiles_count} profiles[/green]")

        if posts_count > 0:
            console.print(f"[cyan]Posts saved to:[/cyan] {site_paths.posts_dir}")
            for post_path in result.get("posts", [])[:5]:  # Show first 5
                console.print(f"  • {Path(post_path).name}")
            if posts_count > 5:
                console.print(f"  ... and {posts_count - 5} more")

    finally:
        if client:
            client.close()
        ibis.options.default_backend = old_backend
        connection.close()


_register_ranking_cli(app)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
