from __future__ import annotations

import logging
import os
import zipfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fire
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

# Imports for config, processor, etc., as in original
from .config import (
    DEFAULT_MODEL,
    AnonymizationConfig,
    CacheConfig,
    EnrichmentConfig,
    LLMConfig,
    PipelineConfig,
    ProfilesConfig,
    SiteConfig,
)
from .processor import UnifiedProcessor
from .rag.config import RAGConfig
from .site_scaffolding import ensure_mkdocs_project

# Constants and console setup as in original
MAX_POSTS_TO_SHOW = 3
# MAX_DATES_TO_SHOW = 10
# QUOTA_WARNING_THRESHOLD = 200
# QUOTA_WARNING_THRESHOLD_ENRICH = 15

console = Console()
logger = logging.getLogger(__name__)


class EgregoraCLI:
    """🤖 Egregora CLI: Transform WhatsApp exports into organized daily posts.

    Processes WhatsApp group exports using AI for structured summaries and enrichment.
    Setup: Obtain Google Gemini API key from https://aistudio.google.com/app/apikey.
    Usage: egregora <subcommand> [options]
        init <output_dir>    Initialize a new MkDocs site scaffold.
        process [options]    Process exports and generate posts.
    """

    def __init__(self):
        self.model: str = DEFAULT_MODEL
        self.timezone: str = "America/Porto_Velho"
        self.disable_enrichment: bool = False
        self.disable_cache: bool = False
        self.link_member_profiles: bool = True
        self.profile_base_url: str = "/profiles/"
        self.safety_threshold: str = "BLOCK_NONE"
        self.thinking_budget: int = -1
        self.max_links: int = 50
        self.relevance_threshold: int = 2
        self.cache_dir: Path = Path("cache")
        self.auto_cleanup_days: int = 90
        self.enable_rag: bool = False

    def init(self, output_dir: str) -> None:
        """Initialize a new MkDocs site scaffold in the specified directory.

        Args:
            output_dir: The directory path for the new site (e.g., 'my-blog').
        """
        site_root = Path(output_dir).resolve()
        site_config = SiteConfig()
        docs_dir, mkdocs_created = ensure_mkdocs_project(site_root, site_config)
        if mkdocs_created:
            console.print(
                Panel(
                    f"[bold green]✅ MkDocs site scaffold initialized successfully![/bold green]\n\n"
                    f"📁 Site root: {site_root}\n"
                    f"📝 Docs directory: {docs_dir}\n\n"
                    f"[bold]Next steps:[/bold]\n"
                    f"• Run [cyan]cd {site_root}[/cyan]\n"
                    f"• Serve the site: [cyan]mkdocs serve[/cyan]\n"
                    f"• Process exports: [cyan]egregora process --zip_files=export.zip --output={output_dir}[/cyan]",
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
        zip_files: str | None = None,  # Comma-separated paths
        output: str | None = None,
        group_name: str | None = None,
        group_slug: str | None = None,
        model: str | None = None,
        timezone: str | None = None,
        days: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        disable_enrichment: bool | None = None,
        disable_cache: bool | None = None,
        dry_run: bool = False,
        link_member_profiles: bool | None = None,
        profile_base_url: str | None = None,
        safety_threshold: str | None = None,
        thinking_budget: int | None = None,
        max_links: int | None = None,
        relevance_threshold: int | None = None,
        cache_dir: str | None = None,
        auto_cleanup_days: int | None = None,
        enable_rag: bool | None = None,
        gemini_key: str | None = None,
        debug: bool = False,
    ) -> None:
        """Process WhatsApp ZIP exports and generate AI-enriched daily posts.

        Args:
            zip_files: Comma-separated WhatsApp .zip export files to process.
            output: Directory where posts will be written.
            group_name: Group name (auto-detected if not provided).
            group_slug: Group slug (auto-generated if not provided).
            model: Gemini model to use.
            timezone: IANA timezone.
            days: Process N most recent days (incompatible with from_date/to_date).
            from_date: Start date (YYYY-MM-DD, incompatible with days).
            to_date: End date (YYYY-MM-DD, incompatible with days).
            disable_enrichment: Disable AI enrichment.
            disable_cache: Disable persistent cache.
            dry_run: Show what would be generated without creating files.
            link_member_profiles: Link member mentions to profile pages.
            profile_base_url: Base URL for profile links.
            safety_threshold: Gemini safety threshold.
            thinking_budget: Gemini thinking budget (-1 for unlimited).
            max_links: Maximum links to enrich per post.
            relevance_threshold: Minimum relevance threshold for enrichment.
            cache_dir: Cache directory path.
            auto_cleanup_days: Auto cleanup cache after N days.
            enable_rag: Enable RAG.
            gemini_key: Google Gemini API key (or use GOOGLE_API_KEY env var).
            debug: Enable detailed logging and stack traces.
        """
        # Configure logging based on debug flag
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[
                RichHandler(
                    console=console,
                    show_path=False,
                    show_level=False,
                    show_time=False,
                    rich_tracebacks=True,
                )
            ],
        )

        # Update instance defaults from parameters
        if model is not None:
            self.model = model
        if timezone is not None:
            self.timezone = timezone
        if disable_enrichment is not None:
            self.disable_enrichment = disable_enrichment
        if disable_cache is not None:
            self.disable_cache = disable_cache
        if link_member_profiles is not None:
            self.link_member_profiles = link_member_profiles
        if profile_base_url is not None:
            self.profile_base_url = profile_base_url
        if safety_threshold is not None:
            self.safety_threshold = safety_threshold
        if thinking_budget is not None:
            self.thinking_budget = thinking_budget
        if max_links is not None:
            self.max_links = max_links
        if relevance_threshold is not None:
            self.relevance_threshold = relevance_threshold
        if cache_dir is not None:
            self.cache_dir = Path(cache_dir)
        if auto_cleanup_days is not None:
            self.auto_cleanup_days = auto_cleanup_days
        if enable_rag is not None:
            self.enable_rag = enable_rag

        # Parse and validate zip_files
        if not zip_files:
            self._error_panel(
                "[yellow]📁 No WhatsApp export files provided![/yellow]\n\n"
                "[bold]How to get WhatsApp export:[/bold]\n"
                "1. Open WhatsApp on your phone\n"
                "2. Go to group chat → Menu (⋮) → More → Export chat\n"
                "3. Choose 'With Media' or 'Without Media'\n"
                "4. Save the .zip file to your computer\n\n"
                "[bold green]Then run:[/bold green]\n"
                "[cyan]egregora process --zip_files=whatsapp-export.zip --gemini_key=YOUR_KEY --output=./my-group-blog[/cyan]\n\n"
                "[bold green]To view your blog:[/bold green]\n"
                "[cyan]cd ./my-group-blog && mkdocs serve[/cyan]",
                "📱 WhatsApp Export Required",
            )
            return
        zip_files_list: list[Path] = [Path(p.strip()) for p in zip_files.split(",")]
        zip_files_list = [p.resolve() for p in zip_files_list]

        # Handle API key
        if gemini_key:
            os.environ["GOOGLE_API_KEY"] = gemini_key
            os.environ["GEMINI_API_KEY"] = gemini_key
        elif not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
            self._error_panel(
                "[red]❌ Google Gemini API key is required![/red]\n\n"
                "[yellow]Get your API key:[/yellow]\n"
                "1. Visit https://aistudio.google.com/app/apikey\n"
                "2. Create and copy your API key\n\n"
                "[yellow]Then either:[/yellow]\n"
                "• Use --gemini_key flag: [cyan]egregora process --gemini_key=YOUR_KEY[/cyan]\n"
                "• Set environment variable: [cyan]export GOOGLE_API_KEY=YOUR_KEY[/cyan]\n"
                "• Add to .env file: [cyan]GOOGLE_API_KEY=YOUR_KEY[/cyan]",
                "🔑 API Key Required",
            )
            return

        # Mutual exclusivity validation
        if days is not None and (from_date is not None or to_date is not None):
            self._error_panel(
                "❌ The --days option cannot be used with --from_date or --to_date.",
                "Invalid Options",
            )
            return

        # Date parsing and validation
        from_date_obj: date | None = None
        to_date_obj: date | None = None
        if from_date:
            try:
                from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
            except ValueError:
                self._error_panel(
                    f"❌ Invalid start date: '{from_date}'. Use YYYY-MM-DD.", "Invalid Date"
                )
                return
        if to_date:
            try:
                to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
            except ValueError:
                self._error_panel(
                    f"❌ Invalid end date: '{to_date}'. Use YYYY-MM-DD.", "Invalid Date"
                )
                return
        if from_date_obj and to_date_obj and from_date_obj > to_date_obj:
            self._error_panel("❌ Start date must be before end date.", "Invalid Date Range")
            return

        days_to_process = days

        # Build nested configuration objects
        llm_config = LLMConfig(
            safety_threshold=safety_threshold or self.safety_threshold,
            thinking_budget=thinking_budget or self.thinking_budget,
        )
        enrichment_config = EnrichmentConfig(
            enabled=not (disable_enrichment or self.disable_enrichment),
            max_links=max_links or self.max_links,
            relevance_threshold=relevance_threshold or self.relevance_threshold,
        )
        cache_config = CacheConfig(
            enabled=not (disable_cache or self.disable_cache),
            cache_dir=Path(cache_dir) if cache_dir else self.cache_dir,
            auto_cleanup_days=auto_cleanup_days or self.auto_cleanup_days,
        )
        profiles_config = ProfilesConfig(
            link_members_in_posts=link_member_profiles or self.link_member_profiles,
            profile_base_url=profile_base_url or self.profile_base_url,
        )

        # Prepare MkDocs scaffold
        site_root = (Path(output) if output else Path("data")).resolve()

        # Create site config
        site_config = SiteConfig()

        docs_dir, mkdocs_created = ensure_mkdocs_project(site_root, site_config)
        if mkdocs_created:
            console.print(f"🛠️  mkdocs.yml created at {site_root / 'mkdocs.yml'}")
        elif docs_dir != site_root:
            console.print(f"📁 Using docs_dir from mkdocs.yml: {docs_dir}")

        config = PipelineConfig(
            zip_files=zip_files_list,
            posts_dir=docs_dir,
            group_name=group_name,
            group_slug=group_slug,
            model=self.model,
            timezone=ZoneInfo(self.timezone),
            llm=llm_config,
            enrichment=enrichment_config,
            cache=cache_config,
            profiles=profiles_config,
            anonymization=AnonymizationConfig(),
            rag=RAGConfig(enabled=enable_rag or self.enable_rag),
            site=site_config,
        )

        # Create processor instance
        processor = UnifiedProcessor(config)

        # Dry run mode


        # Process normally
        try:
            self._process_and_display(
                processor, days=days_to_process, from_date=from_date_obj, to_date=to_date_obj
            )
        except FileNotFoundError as e:
            self._error_panel(
                f"❌ File not found: {str(e).split(': ')[-1]}\n\n[yellow]Please check that:[/yellow]\n• The ZIP file path is correct\n• The file exists and is accessible\n• You have permission to read the file",
                "📁 File Error",
            )
            return
        except IsADirectoryError as e:
            self._error_panel(
                f"❌ Path is a directory, not a ZIP file: {str(e).split(': ')[-1]}\n\n[yellow]Please provide:[/yellow]\n• A path to a .zip file, not a directory\n• The WhatsApp export ZIP file specifically",
                "📁 Directory Error",
            )
            return
        except zipfile.BadZipFile as e:
            self._error_panel(
                f"❌ Invalid ZIP file: {str(e)}\n\n[yellow]Make sure the file is a valid WhatsApp export ZIP[/yellow]",
                "📁 ZIP Error",
            )
            return
        except PermissionError as e:
            self._error_panel(
                f"❌ Permission denied: {str(e).split(': ')[-1]}\n\n[yellow]Check file permissions or try running with appropriate access[/yellow]",
                "🔒 Permission Error",
            )
            return
        except Exception as e:
            self._error_panel(
                f"❌ An error occurred: {str(e)}\n\n[yellow]This might be due to:[/yellow]\n• Invalid ZIP file format\n• Network connectivity issues\n• API key problems\n• Insufficient disk space",
                "⚠️ Processing Error",
            )
            raise  # Preserve traceback for debugging



    def _process_and_display(
        self,
        processor: UnifiedProcessor,
        *,
        days: int | None,
        from_date: date | None,
        to_date: date | None,
    ) -> None:
        """Process groups and show formatted result."""

        # Show quota estimation before processing
        # try:
        #     quota_info = processor.estimate_api_usage(days=days, from_date=from_date, to_date=to_date)
        #     if quota_info["total_api_calls"] > QUOTA_WARNING_THRESHOLD_ENRICH:
        #         console.print(
        #             Panel(
        #                 f"[yellow]⚠️ This operation will make {quota_info['total_api_calls']} API calls[/yellow]\n"
        #                 f"Estimated time (free tier): {quota_info['estimated_time_minutes']:.1f} minutes\n"
        #                 f"[dim]Processing may be interrupted by quota limits.[/dim]",
        #                 border_style="yellow",
        #                 title="Quota Estimation",
        #             )
        #         )

        # except FileNotFoundError:
        #     # Skip quota estimation if file doesn't exist - will be caught later
        #     pass
        # except IsADirectoryError:
        #     # Skip quota estimation if directory instead of ZIP - will be caught later
        #     pass
        # except zipfile.BadZipFile:
        #     # Skip quota estimation if invalid ZIP - will be caught later
        #     pass
        # except Exception as exc:
        #     # Only log other unexpected errors
        #     logger.exception("Failed to estimate quota usage before processing")
        #     console.print(f"\n[yellow]Could not estimate API usage: {exc}[/yellow]")

        # console.print()

        console.print(Panel("[bold green]🚀 Processing Groups[/bold green]"))

        results = processor.process_all(days=days, from_date=from_date, to_date=to_date)

        total = sum(len(v) for v in results.values())
        table = Table(
            title=f"📊 Processing Results ({total} posts generated)",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Group", style="cyan", no_wrap=True)
        table.add_column("Posts Generated", justify="center", style="green")
        table.add_column("Files", style="dim")

        for group_slug, post_paths in results.items():
            files = ", ".join(p.name for p in post_paths[:MAX_POSTS_TO_SHOW])
            if len(post_paths) > MAX_POSTS_TO_SHOW:
                files += f", +{len(post_paths) - MAX_POSTS_TO_SHOW} more"
            table.add_row(group_slug, str(len(post_paths)), files)

        console.print(table)

    def _error_panel(self, content: str, title: str) -> None:
        """Render a standardized Rich error panel."""
        console.print(Panel(content, title=title, border_style="red"))


def main() -> None:
    """CLI entry point."""
    fire.Fire(EgregoraCLI)


def run() -> None:
    """Entry point used by the console script."""
    main()


if __name__ == "__main__":
    main()
