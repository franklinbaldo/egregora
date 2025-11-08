"""Typer-based CLI for Egregora v2."""

import asyncio
import importlib
import json
import logging
import os
import random
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import typer
from google import genai
from jinja2 import Environment, FileSystemLoader
from rich.markup import escape
from rich.panel import Panel

from egregora.agents.editor import run_editor_session
from egregora.agents.loader import load_agent
from egregora.agents.registry import ToolRegistry
from egregora.agents.resolver import AgentResolver
from egregora.agents.tools.profiler import get_active_authors
from egregora.agents.writer import WriterConfig, write_posts_for_window
from egregora.agents.writer.context import _load_profiles_context, _query_rag_for_context
from egregora.agents.writer.formatting import _build_conversation_markdown, _load_freeform_memory
from egregora.config import (
    ModelConfig,
    ProcessConfig,
    RankingCliConfig,
    find_mkdocs_file,
    load_egregora_config,
    load_mkdocs_config,
    resolve_site_paths,
)
from egregora.database import duckdb_backend
from egregora.enrichment import enrich_table, extract_and_replace_media
from egregora.enrichment.core import EnrichmentRuntimeContext
from egregora.ingestion import parse_source  # Phase 6: Renamed from parse_export (alpha - breaking)
from egregora.init import ensure_mkdocs_project
from egregora.pipeline import create_windows
from egregora.pipeline.runner import run_source_pipeline
from egregora.sources.whatsapp import WhatsAppExport, discover_chat_file
from egregora.types import GroupSlug
from egregora.utils.cache import EnrichmentCache
from egregora.utils.logging_setup import configure_logging, console
from egregora.utils.serialization import load_table, save_table

app = typer.Typer(
    name="egregora",
    help="Ultra-simple WhatsApp to blog pipeline with LLM-powered content generation",
    add_completion=False,
)
logger = logging.getLogger(__name__)

# Constants
MAX_POSTS_TO_DISPLAY = 5

# Type alias for JSON-serializable values
JsonValue = (
    None
    | str
    | int
    | float
    | bool
    | datetime
    | date
    | dict[str, Any]
    | list[Any]
    | tuple[Any, ...]
    | set[Any]
)


def _make_json_safe(
    value: JsonValue, *, strict: bool = False
) -> str | int | float | bool | dict[str, Any] | list[Any] | None:
    """Return a JSON-serializable representation of ``value``.

    Args:
        value: Value to convert
        strict: If True, raise TypeError for non-serializable types instead of
                converting to string. Default False for backward compatibility.

    Raises:
        TypeError: If strict=True and value is not JSON-serializable

    """
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _make_json_safe(val, strict=strict) for key, val in value.items()}
    if isinstance(value, list | tuple | set):
        return [_make_json_safe(item, strict=strict) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError, AttributeError) as e:
            logger.debug("Failed to call .item() on %s: %s", type(value).__name__, e)
    if strict:
        msg = f"Cannot serialize type {type(value).__name__} to JSON. Value: {value!r}"
        raise TypeError(msg)
    logger.warning(
        "Converting non-serializable type %s to string for JSON export: %r", type(value).__name__, value
    )
    return str(value)


@app.callback()
def _initialize_cli() -> None:
    """Configure logging when the CLI is invoked."""
    configure_logging()


def _resolve_gemini_key(cli_override: str | None) -> str | None:
    """Return the Gemini API key honoring CLI override precedence.

    If a CLI override is provided, it will be set in the GOOGLE_API_KEY
    environment variable so that all subsequent code (including pydantic-ai
    agents) can access it without explicit passing.
    """
    if cli_override:
        os.environ["GOOGLE_API_KEY"] = cli_override
        return cli_override
    return os.getenv("GOOGLE_API_KEY")


def _validate_retrieval_config(config: ProcessConfig) -> None:
    """Validate and normalize retrieval mode configuration.

    Phase 4: Extracted from _validate_and_run_process to reduce complexity.

    Args:
        config: ProcessConfig to validate (modified in place)

    Raises:
        typer.Exit: If validation fails

    """
    retrieval_mode = (config.retrieval_mode or "ann").lower()
    if retrieval_mode not in {"ann", "exact"}:
        console.print("[red]Invalid retrieval mode. Choose 'ann' or 'exact'.[/red]")
        raise typer.Exit(1)

    if retrieval_mode == "exact" and config.retrieval_nprobe:
        console.print("[yellow]Ignoring retrieval_nprobe: only applicable to ANN search.[/yellow]")
        config.retrieval_nprobe = None

    if config.retrieval_nprobe is not None and config.retrieval_nprobe <= 0:
        console.print("[red]retrieval_nprobe must be positive when provided.[/red]")
        raise typer.Exit(1)

    if config.retrieval_overfetch is not None and config.retrieval_overfetch <= 0:
        console.print("[red]retrieval_overfetch must be positive when provided.[/red]")
        raise typer.Exit(1)

    config.retrieval_mode = retrieval_mode


def _ensure_mkdocs_scaffold(output_dir: Path) -> None:
    """Ensure MkDocs scaffold exists, creating if needed with user confirmation.

    Phase 4: Extracted from _validate_and_run_process to reduce complexity.

    Args:
        output_dir: Output directory to check/initialize

    Raises:
        typer.Exit: If user declines to initialize or initialization fails

    """
    mkdocs_path = find_mkdocs_file(output_dir)
    if mkdocs_path:
        return  # MkDocs scaffold already exists

    output_dir.mkdir(parents=True, exist_ok=True)
    warning_message = (
        f"[yellow]Warning:[/yellow] MkDocs configuration not found in {output_dir}. "
        "Egregora can initialize a new scaffold before processing."
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


@app.command()
def init(
    output_dir: Annotated[Path, typer.Argument(help="Directory path for the new site (e.g., 'my-blog')")],
) -> None:
    """Initialize a new MkDocs site scaffold for serving Egregora posts.

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
                f"[bold green]✅ MkDocs site scaffold initialized successfully![/bold green]\n\n📁 Site root: {site_root}\n📝 Docs directory: {docs_dir}\n\n[bold]Next steps:[/bold]\n• Install MkDocs: [cyan]pip install 'mkdocs-material[imaging]'[/cyan]\n• Change to site directory: [cyan]cd {output_dir}[/cyan]\n• Serve the site: [cyan]mkdocs serve[/cyan]\n• Process WhatsApp export: [cyan]egregora process export.zip --output={output_dir}[/cyan]",
                title="🛠️ Initialization Complete",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold yellow]⚠️ MkDocs site already exists at {site_root}[/bold yellow]\n\n📁 Using existing setup:\n• Docs directory: {docs_dir}\n\n[bold]To update or regenerate:[/bold]\n• Manually edit [cyan]mkdocs.yml[/cyan] or remove it to reinitialize.",
                title="📁 Site Exists",
                border_style="yellow",
            )
        )


def _validate_and_run_process(config: ProcessConfig, source: str = "whatsapp") -> None:
    """Validate process configuration and run the pipeline.

    Phase 4: Simplified by extracting validation logic to helper functions.
    """
    if config.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate timezone
    if config.timezone:
        try:
            ZoneInfo(config.timezone)
            console.print(f"[green]Using timezone: {config.timezone}[/green]")
        except Exception as e:
            console.print(f"[red]Invalid timezone '{config.timezone}': {e}[/red]")
            raise typer.Exit(1) from e

    # Phase 4: Extracted validation logic
    _validate_retrieval_config(config)

    # Resolve and ensure output directory
    output_dir = config.output_dir.expanduser().resolve()
    config.output_dir = output_dir

    # Phase 4: Extracted scaffold initialization logic
    _ensure_mkdocs_scaffold(output_dir)
    api_key = _resolve_gemini_key(config.gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)

    # Load or create EgregoraConfig (Phase 2: reduces parameters)
    base_config = load_egregora_config(output_dir)

    # Override config values from CLI flags using model_copy
    egregora_config = base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(
                update={
                    "step_size": config.step_size,
                    "step_unit": config.step_unit,
                    "overlap_ratio": config.overlap_ratio,
                    "timezone": config.timezone,
                    "from_date": config.from_date.isoformat() if config.from_date else None,
                    "to_date": config.to_date.isoformat() if config.to_date else None,
                    "max_prompt_tokens": config.max_prompt_tokens,
                    "use_full_context_window": config.use_full_context_window,
                }
            ),
            "enrichment": base_config.enrichment.model_copy(update={"enabled": config.enable_enrichment}),
            "rag": base_config.rag.model_copy(
                update={
                    "mode": config.retrieval_mode or base_config.rag.mode,
                    "nprobe": config.retrieval_nprobe
                    if config.retrieval_nprobe is not None
                    else base_config.rag.nprobe,
                    "overfetch": config.retrieval_overfetch
                    if config.retrieval_overfetch is not None
                    else base_config.rag.overfetch,
                }
            ),
        },
    )

    try:
        console.print(
            Panel(
                f"[cyan]Source:[/cyan] {source}\n[cyan]Input:[/cyan] {config.zip_file}\n[cyan]Output:[/cyan] {output_dir}\n[cyan]Windowing:[/cyan] {config.step_size} {config.step_unit}",
                title="⚙️  Egregora Pipeline",
                border_style="cyan",
            )
        )
        run_source_pipeline(
            source=source,
            input_path=config.zip_file,
            output_dir=config.output_dir,
            config=egregora_config,
            api_key=api_key,
            model_override=config.model,
        )
        console.print("[green]Processing completed successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Pipeline failed: {e}[/red]")
        if config.debug:
            raise
        raise typer.Exit(1) from e


@app.command()
def process(  # noqa: PLR0913 - CLI commands naturally have many parameters
    input_file: Annotated[Path, typer.Argument(help="Path to chat export file (ZIP, JSON, etc.)")],
    *,
    source: Annotated[str, typer.Option(help="Source type: 'whatsapp' or 'slack'")] = "whatsapp",
    output: Annotated[Path, typer.Option(help="Output directory for generated site")] = Path("output"),
    step_size: Annotated[int, typer.Option(help="Size of each processing window")] = 1,
    step_unit: Annotated[str, typer.Option(help="Unit for windowing: 'messages', 'hours', 'days'")] = "days",
    overlap: Annotated[
        float, typer.Option(help="Overlap ratio between windows (0.0-0.5, default 0.2 = 20%)")
    ] = 0.2,
    enable_enrichment: Annotated[bool, typer.Option(help="Enable LLM enrichment for URLs/media")] = True,
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
        str | None, typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)")
    ] = None,
    model: Annotated[
        str | None, typer.Option(help="Gemini model to use (or configure in mkdocs.yml)")
    ] = None,
    retrieval_mode: Annotated[
        str, typer.Option(help="Retrieval strategy: 'ann' (default) or 'exact'", case_sensitive=False)
    ] = "ann",
    retrieval_nprobe: Annotated[
        int | None, typer.Option(help="Advanced: override DuckDB VSS nprobe for ANN retrieval")
    ] = None,
    retrieval_overfetch: Annotated[
        int | None, typer.Option(help="Advanced: multiply ANN candidate pool before filtering")
    ] = None,
    max_prompt_tokens: Annotated[
        int, typer.Option(help="Maximum tokens per prompt (default 100k cap, prevents overflow)")
    ] = 100_000,
    use_full_context_window: Annotated[
        bool, typer.Option(help="Use full model context window (overrides --max-prompt-tokens)")
    ] = False,
    debug: Annotated[bool, typer.Option(help="Enable debug logging")] = False,
) -> None:
    """Process chat export and generate blog posts + author profiles.

    Supports multiple sources (WhatsApp, Slack, etc.) via the --source flag.

    Windowing:
        Control how messages are grouped into posts using --step-size and --step-unit:

        By time (default):
            egregora process export.zip --step-size=1 --step-unit=days
            egregora process export.zip --step-size=7 --step-unit=days
            egregora process export.zip --step-size=24 --step-unit=hours

        By message count:
            egregora process export.zip --step-size=100 --step-unit=messages

    The LLM decides:
    - What's worth writing about (filters noise automatically)
    - How many posts per window (0-N)
    - All metadata (title, slug, tags, summary, etc)
    - Which author profiles to update based on contributions
    """
    from_date_obj = None
    to_date_obj = None
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
        except ValueError as e:
            console.print(f"[red]Invalid from_date format: {e}[/red]")
            console.print("[yellow]Expected format: YYYY-MM-DD[/yellow]")
            raise typer.Exit(1) from e
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
        except ValueError as e:
            console.print(f"[red]Invalid to_date format: {e}[/red]")
            console.print("[yellow]Expected format: YYYY-MM-DD[/yellow]")
            raise typer.Exit(1) from e
    config = ProcessConfig(
        zip_file=input_file,
        output_dir=output,
        step_size=step_size,
        step_unit=step_unit,
        overlap_ratio=overlap,
        enable_enrichment=enable_enrichment,
        from_date=from_date_obj,
        to_date=to_date_obj,
        timezone=timezone,
        gemini_key=gemini_key,
        model=model,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        max_prompt_tokens=max_prompt_tokens,
        use_full_context_window=use_full_context_window,
        debug=debug,
    )
    _validate_and_run_process(config, source=source)


@app.command()
def edit(  # noqa: PLR0913 - CLI commands naturally have many parameters
    post_path: Annotated[Path, typer.Argument(help="Path to the post markdown file")],
    *,
    site_dir: Annotated[
        Path | None, typer.Option(help="Site directory (for finding RAG database). Defaults to post parent.")
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            help="Gemini model to use (pydantic-ai format, default: google-gla:gemini-flash-latest)"
        ),
    ] = None,
    gemini_key: Annotated[
        str | None, typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)")
    ] = None,
    agent: Annotated[
        str | None, typer.Option(help="Force a specific agent to be used for the session.")
    ] = None,
    prompt_dry_run: Annotated[
        bool, typer.Option(help="Print the rendered prompt and exit without running the session.")
    ] = False,
) -> None:
    """Interactive LLM-powered editor with RAG and meta-LLM capabilities.

    The editor can:
    - Read and edit posts line-by-line
    - Search similar posts via RAG
    - Make autonomous editing decisions.
    """
    post_file = post_path.resolve()
    if not post_file.exists():
        console.print(f"[red]Post not found: {post_file}[/red]")
        raise typer.Exit(1)
    if site_dir:
        site_path = site_dir.resolve()
    else:
        site_path = post_file.parent
        while site_path.name != "docs":
            site_path = site_path.parent
            if site_path == site_path.parent:
                console.print(
                    "[red]Could not determine site directory. Please specify with --site-dir.[/red]"
                )
                raise typer.Exit(1)
        site_path = site_path.parent
    console.print(f"[cyan]Site directory: {site_path}[/cyan]")
    egregora_path = site_path / ".egregora"
    docs_path = site_path / "docs"
    rag_dir = site_path / "rag"
    if not rag_dir.exists():
        console.print("[yellow]RAG directory not found. Editor will work without RAG.[/yellow]")
    if prompt_dry_run:
        resolver = AgentResolver(egregora_path, docs_path)
        agent_config, prompt_template, final_vars = resolver.resolve(post_file, agent)
        jinja_env = Environment(loader=FileSystemLoader(str(egregora_path)), autoescape=True)
        template = jinja_env.from_string(prompt_template)
        prompt = template.render(final_vars)
        console.print(Panel(prompt, title=f"Prompt for {agent_config.agent_id}", border_style="blue"))
        raise typer.Exit
    api_key = _resolve_gemini_key(gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)
    egregora_config = load_egregora_config(site_path)
    model_config = ModelConfig(config=egregora_config, cli_model=model)
    genai.Client(api_key=api_key)
    try:
        result = asyncio.run(
            run_editor_session(
                post_path=post_file,
                model_config=model_config,
                egregora_path=egregora_path,
                docs_path=docs_path,
                agent_override=agent,
            )
        )
        if result.edits_made:
            post_file.write_text(result.final_content, encoding="utf-8")
            console.print(f"[green]Saved edited content to {post_file}[/green]")
        console.print(
            Panel(
                f"[bold]Editor Session Complete[/bold]\n\nDecision: {result.decision}\nNotes: {result.notes}\nEdits made: {result.edits_made}\nTool calls: {len(result.tool_calls)}",
                title="✅ Done",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Editor session failed: {e}[/red]")
        raise typer.Exit(1) from e


agents_app = typer.Typer(name="agents", help="Manage agents, tools, and skills.")
app.add_typer(agents_app)


@agents_app.command("list")
def agents_list(site_dir: Annotated[Path, typer.Option(help="Site directory")] = Path()) -> None:
    """List all available agents."""
    egregora_path = site_dir.resolve() / ".egregora"
    agents_path = egregora_path / "agents"
    if not agents_path.exists():
        console.print(f"[red]Agents directory not found: {agents_path}[/red]")
        raise typer.Exit(1)
    console.print(Panel("Available Agents", border_style="blue"))
    for agent_file in agents_path.glob("*.jinja"):
        console.print(f"- {agent_file.stem}")


@agents_app.command("explain")
def agents_explain(
    agent_name: Annotated[str, typer.Argument(help="Name of the agent to explain")],
    site_dir: Annotated[Path, typer.Option(help="Site directory")] = Path(),
) -> None:
    """Explain an agent's configuration, tools, and skills."""
    egregora_path = site_dir.resolve() / ".egregora"
    try:
        agent_config, _ = load_agent(agent_name, egregora_path)
        tool_registry = ToolRegistry(egregora_path)
        console.print(Panel(f"Agent: {agent_config.agent_id}", border_style="blue"))
        console.print(f"  Model: {agent_config.model}")
        console.print(f"  Seed: {agent_config.seed}")
        console.print(f"  TTL: {agent_config.ttl}")
        console.print("\n[bold]Variables[/bold]")
        console.print(f"  Defaults: {agent_config.variables.defaults}")
        console.print(f"  Allowed: {agent_config.variables.allowed}")
        toolset = tool_registry.resolve_toolset(agent_config.tools)
        console.print("\n[bold]Tools[/bold]")
        for tool in sorted(toolset):
            console.print(f"  - {tool}")
        skills = agent_config.skills.enable
        console.print("\n[bold]Skills[/bold]")
        for skill in skills:
            console.print(f"  - {skill}")
    except FileNotFoundError:
        console.print(f"[red]Agent '{agent_name}' not found.[/red]")
        raise typer.Exit(1) from None


@agents_app.command("lint")
def agents_lint(site_dir: Annotated[Path, typer.Option(help="Site directory")] = Path()) -> None:
    """Validate the schema of all agents, tools, and skills."""
    egregora_path = site_dir.resolve() / ".egregora"
    errors = 0
    for agent_file in (egregora_path / "agents").glob("*.jinja"):
        try:
            load_agent(agent_file.stem, egregora_path)
        except (FileNotFoundError, ValueError, TypeError, KeyError, OSError, RuntimeError) as e:
            console.print(f"[red]Error in agent {agent_file.name}: {e}[/red]")
            errors += 1
    try:
        ToolRegistry(egregora_path)
    except (FileNotFoundError, ValueError, TypeError, KeyError, OSError, RuntimeError) as e:
        console.print(f"[red]Error loading tool profiles: {e}[/red]")
        errors += 1
    if errors == 0:
        console.print("[green]✅ All agents and tool profiles are valid.[/green]")
    else:
        console.print(f"[red]Found {errors} errors.[/red]")
        raise typer.Exit(1)


def _register_ranking_cli(app: typer.Typer) -> None:  # noqa: C901, PLR0915 - Complex due to nested command registration
    """Register ranking commands when the optional extra is installed."""
    try:
        ranking_agent = importlib.import_module("egregora.agents.ranking")
        ranking_elo = importlib.import_module("egregora.agents.ranking.elo")
        ranking_store_module = importlib.import_module("egregora.agents.ranking.store")
        run_comparison = ranking_agent.run_comparison
        get_posts_to_compare = ranking_elo.get_posts_to_compare
        ranking_store_class = ranking_store_module.RankingStore
    except ModuleNotFoundError as exc:
        missing = exc.name or "egregora.ranking"

        @app.command(hidden=True)
        def rank(
            _site_dir: Annotated[Path, typer.Argument(help="Path to MkDocs site directory")],
            *,
            _comparisons: Annotated[int, typer.Option(help="Number of comparisons to run")] = 1,
            _strategy: Annotated[str, typer.Option(help="Post selection strategy")] = "fewest_games",
            _export_parquet: Annotated[
                bool, typer.Option(help="Export rankings to Parquet after comparisons")
            ] = False,
            _gemini_key: Annotated[
                str | None, typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)")
            ] = None,
            _model: Annotated[
                str | None, typer.Option(help="Gemini model to use (or configure in mkdocs.yml)")
            ] = None,
            _debug: Annotated[bool, typer.Option(help="Enable debug logging")] = False,
        ) -> None:
            install_cmd = escape("pip install 'egregora[ranking]'")
            console.print(f"[red]Ranking commands require the optional extra: {install_cmd}[/red]")
            console.print(f"[yellow]Missing dependency: {escape(missing)}[/yellow]")
            raise typer.Exit(1)

        logger.debug("Ranking extra unavailable: %s", missing)
        return

    def _run_ranking_session(config: RankingCliConfig, gemini_key: str | None) -> None:  # noqa: C901, PLR0915 - Complex ranking loop with error handling
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
        store = ranking_store_class(rankings_dir)
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
        egregora_config = load_egregora_config(site_path)
        model_config = ModelConfig(config=egregora_config, cli_model=config.model)
        ranking_model = model_config.get_model("ranking")
        logger.info("[blue]⚖️  Ranking model:[/] %s", ranking_model)
        for i in range(config.comparisons):
            console.print(
                Panel(
                    f"[bold cyan]Comparison {i + 1} of {config.comparisons}[/bold cyan]", border_style="cyan"
                )
            )
            try:
                post_a_id, post_b_id = get_posts_to_compare(rankings_dir, strategy=config.strategy)
                console.print(f"[cyan]Comparing: {post_a_id} vs {post_b_id}[/cyan]")
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                break
            profile_files = list(profiles_dir.glob("*.md"))
            if not profile_files:
                console.print("[yellow]No profiles found, using default judge[/yellow]")
                default_profile = profiles_dir / "judge.md"
                default_profile.parent.mkdir(parents=True, exist_ok=True)
                default_profile.write_text("---\nuuid: judge\nalias: Judge\n---\nA fair and balanced judge.")
                profile_files = [default_profile]
            profile_path = random.choice(profile_files)  # noqa: S311 - Not cryptographic, just selecting a judge
            try:
                # Import ComparisonConfig dynamically
                comparison_config = ranking_agent.ComparisonConfig(
                    site_dir=site_path,
                    post_a_id=post_a_id,
                    post_b_id=post_b_id,
                    profile_path=profile_path,
                    api_key=api_key,
                    model=ranking_model,
                )
                asyncio.run(run_comparison(comparison_config))
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
                f"[bold]Ranking Statistics:[/bold]\n• Total posts: {stats['total_posts']}\n• Total comparisons: {stats['total_comparisons']}\n• Avg games per post: {stats['avg_games_per_post']:.1f}\n• Highest ELO: {stats['highest_elo']:.0f}\n• Lowest ELO: {stats['lowest_elo']:.0f}",
                title="📊 Rankings",
                border_style="green",
            )
        )

    @app.command()
    def rank(  # noqa: PLR0913 - CLI commands naturally have many parameters
        site_dir: Annotated[Path, typer.Argument(help="Path to MkDocs site directory")],
        *,
        comparisons: Annotated[int, typer.Option(help="Number of comparisons to run")] = 1,
        strategy: Annotated[str, typer.Option(help="Post selection strategy")] = "fewest_games",
        export_parquet: Annotated[
            bool, typer.Option(help="Export rankings to Parquet after comparisons")
        ] = False,
        gemini_key: Annotated[
            str | None, typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)")
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
) -> None:
    """Parse WhatsApp export ZIP to CSV.

    This is the first stage of the pipeline. It:
    - Extracts messages from the ZIP file
    - Parses dates, times, and authors
    - Anonymizes author names to UUID5 pseudonyms
    - Saves structured data to CSV

    Output CSV contains: timestamp, date, author, message, original_line, tagged_line
    """
    zip_path = zip_file.resolve()
    if not zip_path.exists():
        console.print(f"[red]ZIP file not found: {zip_path}[/red]")
        raise typer.Exit(1)
    output_path = output.resolve()
    timezone_obj = None
    if timezone:
        try:
            timezone_obj = ZoneInfo(timezone)
            console.print(f"[green]Using timezone: {timezone}[/green]")
        except Exception as e:
            console.print(f"[red]Invalid timezone '{timezone}': {e}[/red]")
            raise typer.Exit(1) from e
    with duckdb_backend():
        console.print(f"[cyan]Parsing:[/cyan] {zip_path}")
        group_name, chat_file = discover_chat_file(zip_path)
        group_slug = GroupSlug(group_name.lower().replace(" ", "-"))
        console.print(f"[yellow]Group:[/yellow] {group_name}")
        export = WhatsAppExport(
            zip_path=zip_path,
            group_name=group_name,
            group_slug=group_slug,
            export_date=datetime.now(tz=UTC).date(),
            chat_file=chat_file,
            media_files=[],
        )
        messages_table = parse_source(export, timezone=timezone_obj)  # Phase 6: parse_source renamed
        total_messages = messages_table.count().execute()
        console.print(f"[green]✅ Parsed {total_messages} messages[/green]")
        save_table(messages_table, output_path)
        console.print(f"[green]💾 Saved to {output_path}[/green]")


def _parse_date_range(from_date: str | None, to_date: str | None) -> tuple[date | None, date | None]:
    """Parse and validate date range strings.

    Returns:
        Tuple of (from_date_obj, to_date_obj) or (None, None)

    Raises:
        typer.Exit: If date parsing fails

    """
    from_date_obj = None
    to_date_obj = None
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
        except ValueError as e:
            console.print(f"[red]Invalid from_date format: {e}[/red]")
            raise typer.Exit(1) from e
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
        except ValueError as e:
            console.print(f"[red]Invalid to_date format: {e}[/red]")
            raise typer.Exit(1) from e
    return from_date_obj, to_date_obj


def _filter_messages_by_date(
    messages_table: Any, from_date_obj: date | None, to_date_obj: date | None
) -> Any:
    """Filter messages table by date range."""
    if not (from_date_obj or to_date_obj):
        return messages_table

    original_count = messages_table.count().execute()
    if from_date_obj and to_date_obj:
        messages_table = messages_table.filter(
            (messages_table.timestamp.date() >= from_date_obj)
            & (messages_table.timestamp.date() <= to_date_obj)
        )
        console.print(f"[cyan]Filtering:[/cyan] {from_date_obj} to {to_date_obj}")
    elif from_date_obj:
        messages_table = messages_table.filter(messages_table.timestamp.date() >= from_date_obj)
        console.print(f"[cyan]Filtering:[/cyan] from {from_date_obj}")
    elif to_date_obj:
        messages_table = messages_table.filter(messages_table.timestamp.date() <= to_date_obj)
        console.print(f"[cyan]Filtering:[/cyan] up to {to_date_obj}")

    filtered_count = messages_table.count().execute()
    removed = original_count - filtered_count
    console.print(f"[yellow]Filtered out {removed} messages (kept {filtered_count})[/yellow]")
    return messages_table


@app.command()
def group(  # noqa: PLR0913
    input_csv: Annotated[Path, typer.Argument(help="Input CSV file from parse stage")],
    step_size: Annotated[int, typer.Option(help="Size of each processing window")] = 1,
    step_unit: Annotated[str, typer.Option(help="Unit for windowing: 'messages', 'hours', 'days'")] = "days",
    output_dir: Annotated[Path, typer.Option(help="Output directory for window CSV files")] = Path("windows"),
    from_date: Annotated[
        str | None, typer.Option(help="Only include messages from this date onwards (YYYY-MM-DD)")
    ] = None,
    to_date: Annotated[
        str | None, typer.Option(help="Only include messages up to this date (YYYY-MM-DD)")
    ] = None,
) -> None:
    """Group messages into processing windows.

    This is the second stage of the pipeline. It:
    - Loads messages from CSV
    - Optionally filters by date range
    - Groups messages into windows based on step_size and step_unit
    - Saves each window to a separate CSV file

    Output files are named by window start time: window_YYYYMMDD_HHMMSS.csv

    Examples:
        egregora group messages.csv --step-size=1 --step-unit=days
        egregora group messages.csv --step-size=7 --step-unit=days
        egregora group messages.csv --step-size=100 --step-unit=messages

    """
    input_path = input_csv.resolve()
    if not input_path.exists():
        console.print(f"[red]Input file not found: {input_path}[/red]")
        raise typer.Exit(1)
    if step_unit not in {"messages", "hours", "days"}:
        console.print(f"[red]Invalid step_unit '{step_unit}'. Choose: messages, hours, or days[/red]")
        raise typer.Exit(1)
    output_path = output_dir.resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    from_date_obj, to_date_obj = _parse_date_range(from_date, to_date)
    with duckdb_backend():
        console.print(f"[cyan]Loading:[/cyan] {input_path}")
        messages_table = load_table(input_path)
        messages_table = _filter_messages_by_date(messages_table, from_date_obj, to_date_obj)
        console.print(f"[cyan]Creating windows:[/cyan] step_size={step_size}, unit={step_unit}")
        windows_generator = create_windows(
            messages_table,
            step_size=step_size,
            step_unit=step_unit,
        )
        # Collect generator into list (create_windows returns generator, not dict)
        windows = list(windows_generator)
        if not windows:
            console.print("[yellow]No windows found after grouping[/yellow]")
            raise typer.Exit(0)
        console.print(f"[green]Found {len(windows)} windows[/green]")
        for window in windows:
            # Generate filename from timestamps (window has no string ID)
            window_filename = f"window_{window.start_time:%Y%m%d_%H%M%S}"
            window_output = output_path / f"{window_filename}.csv"
            window_count = window.size
            window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
            console.print(f"  [cyan]{window_label}:[/cyan] {window_count} messages → {window_output}")
            save_table(window.table, window_output)
        console.print(f"[green]✅ Saved {len(windows)} window files to {output_path}[/green]")


@app.command()
def enrich(  # noqa: PLR0913, PLR0915 - CLI command with many parameters and statements
    input_csv: Annotated[Path, typer.Argument(help="Input CSV file (from parse or group stage)")],
    *,
    zip_file: Annotated[Path, typer.Option(help="Original WhatsApp ZIP file (for media extraction)")],
    output: Annotated[Path, typer.Option(help="Output enriched CSV file")],
    site_dir: Annotated[Path, typer.Option(help="Site directory (for media storage)")],
    gemini_key: Annotated[
        str | None, typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)")
    ] = None,
    enable_url: Annotated[bool, typer.Option(help="Enable URL enrichment")] = True,
    enable_media: Annotated[bool, typer.Option(help="Enable media enrichment")] = True,
    max_enrichments: Annotated[int, typer.Option(help="Maximum number of enrichments to perform")] = 50,
) -> None:
    """Enrich messages with LLM-generated context for URLs and media.

    This is the third stage of the pipeline. It:
    - Loads messages from CSV
    - Extracts media files from the ZIP
    - Optionally enriches URLs with LLM descriptions
    - Optionally enriches media (images/videos) with LLM descriptions
    - Adds enrichment as new rows (author='egregora')
    - Saves enriched table to CSV

    Requires GOOGLE_API_KEY environment variable or --gemini-key flag.
    """
    input_path = input_csv.resolve()
    if not input_path.exists():
        console.print(f"[red]Input file not found: {input_path}[/red]")
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
    api_key = _resolve_gemini_key(gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)
    site_paths = resolve_site_paths(site_path)
    posts_dir = site_paths.posts_dir
    egregora_config = load_egregora_config(site_path)
    ModelConfig(config=egregora_config)
    client: genai.Client | None = None
    enrichment_cache: EnrichmentCache | None = None
    try:
        with duckdb_backend():
            client = genai.Client(api_key=api_key)
            console.print(f"[cyan]Loading:[/cyan] {input_path}")
            messages_table = load_table(input_path)
            original_count = messages_table.count().execute()
            console.print(f"[cyan]Loaded {original_count} messages[/cyan]")
            console.print("[yellow]Extracting media from ZIP...[/yellow]")
            messages_table, media_mapping = extract_and_replace_media(
                messages_table, zip_path, site_paths.docs_dir, posts_dir, "chat"
            )
            console.print(f"[green]Extracted {len(media_mapping)} media files[/green]")
            cache_dir = Path(".egregora-cache") / site_paths.site_root.name
            enrichment_cache = EnrichmentCache(cache_dir)
            console.print(
                f"[cyan]Enriching with:[/cyan] URLs={enable_url}, Media={enable_media}, Max={max_enrichments}"
            )

            # Phase 4: Use modern signature (4 params: table, media_mapping, config, context)
            # Override enrichment settings from CLI flags
            cli_config = egregora_config.model_copy(
                deep=True,
                update={
                    "enrichment": egregora_config.enrichment.model_copy(
                        update={
                            "enable_url": enable_url,
                            "enable_media": enable_media,
                            "max_enrichments": max_enrichments,
                        }
                    )
                },
            )
            enrichment_context = EnrichmentRuntimeContext(
                cache=enrichment_cache,
                docs_dir=site_paths.docs_dir,
                posts_dir=posts_dir,
            )
            enriched_table = enrich_table(
                messages_table,
                media_mapping,
                cli_config,
                enrichment_context,
            )
            enriched_count = enriched_table.count().execute()
            added_rows = enriched_count - original_count
            console.print(f"[green]✅ Added {added_rows} enrichment rows[/green]")
            save_table(enriched_table, output_path)
            console.print(f"[green]💾 Saved to {output_path}[/green]")
    finally:
        if enrichment_cache:
            enrichment_cache.close()
        if client:
            client.close()


@app.command()
def gather_context(  # noqa: PLR0913, PLR0915 - CLI command with many parameters and statements
    input_csv: Annotated[Path, typer.Argument(help="Input enriched CSV file")],
    *,
    window_id: Annotated[str, typer.Option(help="Window identifier (e.g., 2025-01-01 or custom label)")],
    site_dir: Annotated[Path, typer.Option(help="Site directory")],
    output: Annotated[Path, typer.Option(help="Output context JSON file")],
    gemini_key: Annotated[
        str | None, typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)")
    ] = None,
    enable_rag: Annotated[bool, typer.Option(help="Enable RAG retrieval")] = True,
    retrieval_mode: Annotated[str, typer.Option(help="Retrieval strategy: 'ann' or 'exact'")] = "ann",
    retrieval_nprobe: Annotated[int | None, typer.Option(help="DuckDB VSS nprobe for ANN")] = None,
    retrieval_overfetch: Annotated[int | None, typer.Option(help="Multiply ANN candidate pool")] = None,
) -> None:
    """Gather context for post generation (RAG, profiles, freeform memory).

    This is the fourth stage of the pipeline. It:
    - Loads enriched messages from CSV
    - Formats conversation as markdown table
    - Queries RAG for similar posts (if enabled)
    - Loads author profiles
    - Loads freeform memory from previous windows
    - Loads site configuration
    - Saves all context to JSON file

    The JSON output can be inspected and reused for multiple generation runs.
    """
    input_path = input_csv.resolve()
    if not input_path.exists():
        console.print(f"[red]Input file not found: {input_path}[/red]")
        raise typer.Exit(1)
    site_path = site_dir.resolve()
    if not site_path.exists():
        console.print(f"[red]Site directory not found: {site_path}[/red]")
        raise typer.Exit(1)
    output_path = output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    site_paths = resolve_site_paths(site_path)
    egregora_config = load_egregora_config(site_path)
    model_config = ModelConfig(config=egregora_config)
    mkdocs_config = load_mkdocs_config(site_path)
    client: genai.Client | None = None
    try:
        with duckdb_backend():
            console.print(f"[cyan]Loading:[/cyan] {input_path}")
            enriched_table = load_table(input_path)
            message_count = enriched_table.count().execute()
            console.print(f"[cyan]Loaded {message_count} messages[/cyan]")
            console.print("[yellow]Formatting conversation...[/yellow]")
            conversation_md = _build_conversation_markdown(enriched_table.to_pyarrow(), None)
            active_authors = get_active_authors(enriched_table)
            console.print(f"[cyan]Active authors: {len(active_authors)}[/cyan]")
            console.print("[yellow]Loading profiles...[/yellow]")
            profiles = _load_profiles_context(enriched_table, site_paths.profiles_dir)
            console.print("[yellow]Loading freeform memory...[/yellow]")
            posts_output_dir = site_paths.posts_dir
            freeform_memory = _load_freeform_memory(posts_output_dir)
            rag_similar_posts: list[dict[str, Any]] = []
            rag_context_markdown = ""
            if enable_rag:
                api_key = _resolve_gemini_key(gemini_key)
                if not api_key:
                    console.print(
                        "[yellow]Warning: RAG enabled but no API key provided, skipping RAG[/yellow]"
                    )
                else:
                    console.print("[yellow]Querying RAG for similar posts...[/yellow]")
                    client = genai.Client(api_key=api_key)
                    rag_context_markdown, rag_similar_posts = _query_rag_for_context(
                        enriched_table,
                        client,
                        site_paths.rag_dir,
                        embedding_model=model_config.get_model("embedding"),
                        retrieval_mode=retrieval_mode,
                        retrieval_nprobe=retrieval_nprobe,
                        retrieval_overfetch=retrieval_overfetch,
                        return_records=True,
                    )
                    console.print(f"[green]Found {len(rag_similar_posts)} similar posts[/green]")
            if rag_similar_posts:
                rag_similar_posts = [_make_json_safe(record) for record in rag_similar_posts]
            context = {
                "window_id": window_id,
                "conversation_markdown": conversation_md,
                "active_authors": list(active_authors),
                "profiles": profiles,
                "freeform_memory": freeform_memory,
                "rag_similar_posts": rag_similar_posts,
                "rag_context_markdown": rag_context_markdown,
                "site_config": {
                    "markdown_extensions": mkdocs_config.get("markdown_extensions", []),
                    "custom_writer_prompt": mkdocs_config.get("extra", {})
                    .get("egregora", {})
                    .get("custom_writer_prompt"),
                },
                "message_count": message_count,
            }
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(context, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✅ Saved context to {output_path}[/green]")
            console.print("[cyan]Context includes:[/cyan]")
            console.print(f"  • {message_count} messages")
            console.print(f"  • {len(active_authors)} active authors")
            console.print(f"  • {len(rag_similar_posts)} RAG results")
            console.print(f"  • Freeform memory: {('Yes' if freeform_memory else 'No')}")
    finally:
        if client:
            client.close()


@app.command()
def write_posts(  # noqa: PLR0913, PLR0915 - CLI command with many parameters and statements
    input_csv: Annotated[Path, typer.Argument(help="Input enriched CSV file")],
    *,
    window_id: Annotated[str, typer.Option(help="Window identifier (e.g., 2025-01-01 or custom label)")],
    site_dir: Annotated[Path, typer.Option(help="Site directory")],
    context: Annotated[
        Path | None, typer.Option(help="Context JSON file (from gather-context command)")
    ] = None,
    gemini_key: Annotated[
        str | None, typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)")
    ] = None,
    model: Annotated[str | None, typer.Option(help="Gemini model to use (overrides mkdocs.yml)")] = None,
    enable_rag: Annotated[bool, typer.Option(help="Enable RAG retrieval")] = True,
    retrieval_mode: Annotated[str, typer.Option(help="Retrieval strategy: 'ann' or 'exact'")] = "ann",
    retrieval_nprobe: Annotated[int | None, typer.Option(help="DuckDB VSS nprobe for ANN")] = None,
    retrieval_overfetch: Annotated[int | None, typer.Option(help="Multiply ANN candidate pool")] = None,
) -> None:
    """Generate blog posts from enriched messages using LLM.

    This is the fifth (final) stage of the pipeline. It:
    - Loads enriched messages from CSV
    - Loads context from JSON (if provided) or gathers inline
    - Invokes LLM with write_post tool for editorial control
    - LLM decides: what to write, how many posts, all metadata
    - Saves posts to site-dir/docs/posts/
    - Updates profiles in site-dir/docs/profiles/

    The LLM has full editorial control via function calling.
    """
    input_path = input_csv.resolve()
    if not input_path.exists():
        console.print(f"[red]Input file not found: {input_path}[/red]")
        raise typer.Exit(1)
    site_path = site_dir.resolve()
    if not site_path.exists():
        console.print(f"[red]Site directory not found: {site_path}[/red]")
        raise typer.Exit(1)
    context_path = context.resolve() if context else None
    if context_path and (not context_path.exists()):
        console.print(f"[red]Context file not found: {context_path}[/red]")
        raise typer.Exit(1)
    api_key = _resolve_gemini_key(gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)
    site_paths = resolve_site_paths(site_path)
    egregora_config = load_egregora_config(site_path)
    model_config = ModelConfig(config=egregora_config, cli_model=model)
    client: genai.Client | None = None
    try:
        with duckdb_backend():
            client = genai.Client(api_key=api_key)
            console.print(f"[cyan]Loading:[/cyan] {input_path}")
            enriched_table = load_table(input_path)
            message_count = enriched_table.count().execute()
            console.print(f"[cyan]Loaded {message_count} messages[/cyan]")
            if context_path:
                console.print(f"[cyan]Using context from:[/cyan] {context_path}")
                with context_path.open("r", encoding="utf-8") as f:
                    context_data = json.load(f)
                rag_count = len(context_data.get("rag_similar_posts", []))
                console.print(f"[yellow]Context includes {rag_count} RAG results[/yellow]")
            else:
                console.print("[yellow]No context file provided, will gather context inline[/yellow]")
            console.print(f"[cyan]Writer model:[/cyan] {model_config.get_model('writer')}")
            console.print(f"[cyan]RAG retrieval:[/cyan] {('enabled' if enable_rag else 'disabled')}")
            # Extract time range from data for writer context
            start_time = enriched_table.timestamp.min().execute()
            end_time = enriched_table.timestamp.max().execute()
            window_label = f"{start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}"

            console.print(f"[yellow]Invoking LLM writer for window {window_label}...[/yellow]")
            writer_config = WriterConfig(
                output_dir=site_paths.posts_dir,
                profiles_dir=site_paths.profiles_dir,
                rag_dir=site_paths.rag_dir,
                site_root=site_paths.site_root,
                model_config=model_config,
                enable_rag=enable_rag,
                retrieval_mode=retrieval_mode,
                retrieval_nprobe=retrieval_nprobe,
                retrieval_overfetch=retrieval_overfetch,
            )
            result = write_posts_for_window(enriched_table, start_time, end_time, client, writer_config)
            posts_count = len(result.get("posts", []))
            profiles_count = len(result.get("profiles", []))
            console.print(f"[green]✅ Generated {posts_count} posts[/green]")
            console.print(f"[green]✅ Updated {profiles_count} profiles[/green]")
            if posts_count > 0:
                console.print(f"[cyan]Posts saved to:[/cyan] {site_paths.posts_dir}")
                for post_path in result.get("posts", [])[:MAX_POSTS_TO_DISPLAY]:
                    console.print(f"  • {Path(post_path).name}")
                if posts_count > MAX_POSTS_TO_DISPLAY:
                    console.print(f"  ... and {posts_count - MAX_POSTS_TO_DISPLAY} more")
    finally:
        if client:
            client.close()


_register_ranking_cli(app)


# ==============================================================================
# Diagnostics Command
# ==============================================================================


@app.command(name="doctor")
def doctor(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show detailed diagnostic information")] = False,
) -> None:
    """Run diagnostic checks to verify Egregora setup.

    Checks:
    - Python version (3.12+)
    - Required packages
    - API key configuration
    - DuckDB VSS extension
    - Git availability
    - Cache directory permissions
    - Egregora config validity
    - Available source adapters

    Examples:
        egregora doctor          # Run all checks
        egregora doctor -v       # Show detailed output
    """
    from egregora.diagnostics import HealthStatus, run_diagnostics

    console.print("[bold cyan]Running diagnostics...[/bold cyan]")
    console.print()

    results = run_diagnostics()

    # Count status levels
    ok_count = sum(1 for r in results if r.status == HealthStatus.OK)
    warning_count = sum(1 for r in results if r.status == HealthStatus.WARNING)
    error_count = sum(1 for r in results if r.status == HealthStatus.ERROR)

    # Display results
    for result in results:
        # Status icon and color
        if result.status == HealthStatus.OK:
            icon = "✅"
            color = "green"
        elif result.status == HealthStatus.WARNING:
            icon = "⚠️"
            color = "yellow"
        elif result.status == HealthStatus.ERROR:
            icon = "❌"
            color = "red"
        else:  # INFO
            icon = "ℹ️"
            color = "cyan"

        # Print check result
        console.print(f"[{color}]{icon} {result.check}:[/{color}] {result.message}")

        # Show details if verbose
        if verbose and result.details:
            for key, value in result.details.items():
                console.print(f"    {key}: {value}", style="dim")

    # Summary
    console.print()
    if error_count == 0 and warning_count == 0:
        console.print("[bold green]✅ All checks passed! Egregora is ready to use.[/bold green]")
    elif error_count == 0:
        console.print(f"[bold yellow]⚠️  {warning_count} warning(s) found. Egregora should work but some features may be limited.[/bold yellow]")
    else:
        console.print(f"[bold red]❌ {error_count} error(s) found. Please fix these issues before using Egregora.[/bold red]")

    console.print()
    console.print(f"[dim]Summary: {ok_count} OK, {warning_count} warnings, {error_count} errors[/dim]")

    # Exit with error code if any errors found
    if error_count > 0:
        raise typer.Exit(1)


# ==============================================================================
# Cache Management Commands
# ==============================================================================

cache_app = typer.Typer(
    name="cache",
    help="Manage pipeline checkpoints and cache",
)
app.add_typer(cache_app)


@cache_app.command(name="stats")
def cache_stats(
    cache_dir: Annotated[
        Path, typer.Option(help="Checkpoint cache directory")
    ] = Path(".egregora-cache/checkpoints"),
) -> None:
    """Show cache statistics (size, count, per-stage breakdown)."""
    from egregora.pipeline.checkpoint import get_cache_stats

    stats = get_cache_stats(cache_dir=cache_dir)

    if stats["total_count"] == 0:
        console.print("[yellow]Cache is empty[/yellow]")
        return

    # Display total stats
    total_mb = stats["total_size"] / (1024**2)
    console.print(f"[cyan]Total cache size:[/cyan] {total_mb:.2f} MB")
    console.print(f"[cyan]Total checkpoints:[/cyan] {stats['total_count']}")
    console.print()

    # Per-stage breakdown
    if stats["stages"]:
        console.print("[cyan]Per-stage breakdown:[/cyan]")
        for stage_name, stage_stats in sorted(stats["stages"].items()):
            stage_mb = stage_stats["size"] / (1024**2)
            console.print(f"  • {stage_name}: {stage_stats['count']} checkpoints, {stage_mb:.2f} MB")


@cache_app.command(name="clear")
def cache_clear(
    stage: Annotated[str | None, typer.Option(help="Stage to clear (clears all if not specified)")] = None,
    cache_dir: Annotated[
        Path, typer.Option(help="Checkpoint cache directory")
    ] = Path(".egregora-cache/checkpoints"),
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
) -> None:
    """Clear checkpoints (cache invalidation).

    Examples:
        egregora cache clear --stage=enrichment   # Clear only enrichment checkpoints
        egregora cache clear                      # Clear all checkpoints
        egregora cache clear --force              # Skip confirmation
    """
    from egregora.pipeline.checkpoint import clear_checkpoints, get_cache_stats

    # Get stats before clearing
    stats = get_cache_stats(cache_dir=cache_dir)

    if stats["total_count"] == 0:
        console.print("[yellow]Cache is already empty[/yellow]")
        return

    # Confirm before clearing (unless --force)
    if not force:
        if stage:
            stage_stats = stats["stages"].get(stage, {"count": 0, "size": 0})
            if stage_stats["count"] == 0:
                console.print(f"[yellow]No checkpoints found for stage '{stage}'[/yellow]")
                return
            stage_mb = stage_stats["size"] / (1024**2)
            console.print(f"[yellow]About to delete {stage_stats['count']} checkpoints ({stage_mb:.2f} MB) for stage '{stage}'[/yellow]")
        else:
            total_mb = stats["total_size"] / (1024**2)
            console.print(f"[yellow]About to delete all {stats['total_count']} checkpoints ({total_mb:.2f} MB)[/yellow]")

        confirm = typer.confirm("Continue?")
        if not confirm:
            console.print("[cyan]Cancelled[/cyan]")
            raise typer.Exit(0)

    # Clear checkpoints
    count = clear_checkpoints(stage=stage, cache_dir=cache_dir)
    console.print(f"[green]✅ Deleted {count} checkpoints[/green]")


@cache_app.command(name="gc")
def cache_gc(
    keep_last: Annotated[
        int | None, typer.Option(help="Keep last N checkpoints per stage (age-based GC)")
    ] = None,
    max_size: Annotated[
        str | None, typer.Option(help="Maximum cache size (e.g., '10GB', '500MB')")
    ] = None,
    stage: Annotated[str | None, typer.Option(help="Stage to garbage collect (applies to all if not specified)")] = None,
    cache_dir: Annotated[
        Path, typer.Option(help="Checkpoint cache directory")
    ] = Path(".egregora-cache/checkpoints"),
) -> None:
    """Garbage collect old checkpoints.

    Use --keep-last for age-based GC (keep N most recent per stage).
    Use --max-size for size-based GC (LRU eviction until under limit).

    Examples:
        egregora cache gc --keep-last=5               # Keep last 5 checkpoints per stage
        egregora cache gc --keep-last=3 --stage=enrichment  # Keep last 3 enrichment checkpoints
        egregora cache gc --max-size=10GB             # Keep cache under 10 GB
        egregora cache gc --max-size=500MB            # Keep cache under 500 MB
    """
    from egregora.pipeline.checkpoint import gc_checkpoints_by_age, gc_checkpoints_by_size

    if keep_last is None and max_size is None:
        console.print("[red]Error: Must specify either --keep-last or --max-size[/red]")
        console.print("Examples:")
        console.print("  egregora cache gc --keep-last=5")
        console.print("  egregora cache gc --max-size=10GB")
        raise typer.Exit(1)

    if keep_last is not None and max_size is not None:
        console.print("[red]Error: Cannot use both --keep-last and --max-size (choose one)[/red]")
        raise typer.Exit(1)

    if keep_last is not None:
        # Age-based GC
        console.print(f"[cyan]Garbage collecting checkpoints (keeping last {keep_last} per stage)...[/cyan]")
        count = gc_checkpoints_by_age(stage=stage, keep_last=keep_last, cache_dir=cache_dir)
        console.print(f"[green]✅ Deleted {count} old checkpoints[/green]")

    elif max_size is not None:
        # Size-based GC
        # Parse max_size (e.g., "10GB", "500MB")
        max_size_upper = max_size.upper()
        try:
            if max_size_upper.endswith("GB"):
                max_size_bytes = int(float(max_size_upper[:-2]) * 1024**3)
            elif max_size_upper.endswith("MB"):
                max_size_bytes = int(float(max_size_upper[:-2]) * 1024**2)
            elif max_size_upper.endswith("KB"):
                max_size_bytes = int(float(max_size_upper[:-2]) * 1024)
            elif max_size_upper.endswith("B"):
                max_size_bytes = int(max_size_upper[:-1])
            else:
                # Try parsing as raw bytes
                max_size_bytes = int(max_size)
        except ValueError:
            console.print(f"[red]Error: Invalid size format '{max_size}'[/red]")
            console.print("Valid formats: '10GB', '500MB', '1KB', or raw bytes")
            raise typer.Exit(1)

        console.print(f"[cyan]Garbage collecting checkpoints (max size: {max_size})...[/cyan]")
        count = gc_checkpoints_by_size(max_size_bytes=max_size_bytes, cache_dir=cache_dir)
        console.print(f"[green]✅ Deleted {count} checkpoints to stay under size limit[/green]")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
