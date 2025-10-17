"""Enhanced command line interface for Egregora with subcommands using Fire."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fire
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from .config import (
    DEFAULT_MODEL,
    AnonymizationConfig,
    CacheConfig,
    EnrichmentConfig,
    LLMConfig,
    PipelineConfig,
    ProfilesConfig,
)
from .processor import UnifiedProcessor
from .rag.config import RAGConfig
from .site_scaffolding import ensure_mkdocs_project

MAX_POSTS_TO_SHOW = 3
MAX_DATES_TO_SHOW = 10
QUOTA_WARNING_THRESHOLD = 200
QUOTA_WARNING_THRESHOLD_ENRICH = 15

console = Console()

# Configure logging to use Rich for pretty output
logging.basicConfig(
    level=logging.INFO,
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

logger = logging.getLogger(__name__)


class EgregoraCLI:
    """🤖 Egregora - Transform WhatsApp exports into organized daily posts

    Egregora processes WhatsApp group exports and uses AI to create structured daily summaries,
    enriched with context and member profiles. Perfect for communities, study groups, and teams
    that want to preserve and organize their conversations.

    SETUP:
      Get your Google Gemini API key from https://aistudio.google.com/app/apikey
      
      Options to provide API key:
      • --gemini_key flag: egregora process --zip_files=file.zip --gemini_key=YOUR_KEY
      • Environment variable: export GOOGLE_API_KEY="your-key"  
      • .env file: GOOGLE_API_KEY=your-key

    TYPICAL USAGE:
      egregora process --zip_files=whatsapp-export.zip --gemini_key=YOUR_API_KEY --output=./my-group-blog
    """

    def process(
        self,
        zip_files=None,
        output=None,
        group_name=None,
        group_slug=None,
        model=DEFAULT_MODEL,
        timezone="America/Porto_Velho",
        days=None,
        from_date=None,
        to_date=None,
        disable_enrichment=False,
        disable_cache=False,
        list_groups=False,
        dry_run=False,
        link_member_profiles=True,
        profile_base_url="/profiles/",
        safety_threshold="BLOCK_NONE",
        thinking_budget=-1,
        max_links=50,
        relevance_threshold=2,
        cache_dir="cache",
        auto_cleanup_days=90,
        enable_rag=False,
        gemini_key=None,
        debug=False,
    ):
        """Process WhatsApp .zip exports and generate organized daily posts with AI enrichment.

        Args:
            zip_files: Comma-separated WhatsApp .zip export files to process
            output: Directory where posts will be written
            group_name: Group name (auto-detected if not provided)
            group_slug: Group slug (auto-generated if not provided)
            model: Gemini model to use
            timezone: IANA timezone
            days: Process N most recent days (incompatible with from_date/to_date)
            from_date: Start date (YYYY-MM-DD, incompatible with days)
            to_date: End date (YYYY-MM-DD, incompatible with days)
            disable_enrichment: Disable AI enrichment
            disable_cache: Disable persistent cache
            list_groups: List discovered groups and exit
            dry_run: Show what would be generated without creating files
            link_member_profiles: Link member mentions to profile pages
            profile_base_url: Base URL for profile links
            safety_threshold: Gemini safety threshold
            thinking_budget: Gemini thinking budget (-1 for unlimited)
            max_links: Maximum links to enrich per post
            relevance_threshold: Minimum relevance threshold for enrichment
            cache_dir: Cache directory path
            auto_cleanup_days: Auto cleanup cache after N days
            enable_rag: Enable RAG
            gemini_key: Google Gemini API key
            debug: Show detailed error messages and stack traces
        """

        # Parse zip_files as list if provided as comma-separated string
        if zip_files:
            if isinstance(zip_files, str):
                zip_files = [Path(p.strip()) for p in zip_files.split(",")]
            else:
                zip_files = [Path(p) for p in zip_files]

        # Check if ZIP files are provided
        if not zip_files:
            console.print(Panel(
                "[yellow]📁 No WhatsApp export files provided![/yellow]\n\n"
                "[bold]How to get WhatsApp export:[/bold]\n"
                "1. Open WhatsApp on your phone\n"
                "2. Go to group chat → Menu (⋮) → More → Export chat\n"
                "3. Choose 'With Media' or 'Without Media'\n"
                "4. Save the .zip file to your computer\n\n"
                "[bold green]Then run:[/bold green]\n"
                "[cyan]egregora process --zip_files=whatsapp-export.zip --gemini_key=YOUR_API_KEY --output=./my-group-blog[/cyan]\n\n"
                "[bold green]To view your blog:[/bold green]\n"
                "[cyan]cd ./my-group-blog && mkdocs serve[/cyan]",
                title="📱 WhatsApp Export Required",
                border_style="yellow"
            ))
            return

        # Handle API key
        if gemini_key:
            os.environ["GOOGLE_API_KEY"] = gemini_key
        elif not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
            console.print(Panel(
                "[red]❌ Google Gemini API key is required![/red]\n\n"
                "[yellow]Get your API key:[/yellow]\n"
                "1. Visit https://aistudio.google.com/app/apikey\n"
                "2. Create and copy your API key\n\n"
                "[yellow]Then either:[/yellow]\n"
                "• Use --gemini_key flag: [cyan]egregora process --zip_files=file.zip --gemini_key=YOUR_KEY[/cyan]\n"
                "• Set environment variable: [cyan]export GOOGLE_API_KEY=YOUR_KEY[/cyan]\n"
                "• Add to .env file: [cyan]GOOGLE_API_KEY=YOUR_KEY[/cyan]",
                title="🔑 API Key Required",
                border_style="red"
            ))
            return

        # Mutual exclusivity validation
        if days is not None and (from_date is not None or to_date is not None):
            console.print("❌ The --days option cannot be used with --from_date or --to_date.")
            return

        # Date parsing and validation
        from_date_obj = None
        to_date_obj = None

        if from_date:
            try:
                from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
            except ValueError as e:
                console.print(f"❌ Invalid start date: '{from_date}'. Use YYYY-MM-DD.")
                return

        if to_date:
            try:
                to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
            except ValueError as e:
                console.print(f"❌ Invalid end date: '{to_date}'. Use YYYY-MM-DD.")
                return

        # Date range validation
        if from_date_obj and to_date_obj and from_date_obj > to_date_obj:
            console.print("❌ Start date must be before end date.")
            return

        # Convert days to days_to_process for backward compatibility
        days_to_process = days

        # Normalize input paths
        zip_files = [path.resolve() for path in zip_files]

        # Build nested configuration objects
        llm_config = LLMConfig(safety_threshold=safety_threshold, thinking_budget=thinking_budget)

        enrichment_config = EnrichmentConfig(
            enabled=not disable_enrichment, max_links=max_links, relevance_threshold=relevance_threshold
        )

        cache_config = CacheConfig(
            enabled=not disable_cache, cache_dir=Path(cache_dir), auto_cleanup_days=auto_cleanup_days
        )

        profiles_config = ProfilesConfig(
            link_members_in_posts=link_member_profiles, profile_base_url=profile_base_url
        )

        # Prepare MkDocs scaffold (or reuse an existing one)
        site_root = (Path(output) if output else Path("data")).resolve()
        docs_dir, mkdocs_created = ensure_mkdocs_project(site_root)
        if mkdocs_created:
            console.print(f"🛠️  mkdocs.yml created at {site_root / 'mkdocs.yml'}")
        elif docs_dir != site_root:
            console.print(f"📁 Using docs_dir from mkdocs.yml: {docs_dir}")

        config = PipelineConfig(
            zip_files=zip_files,
            posts_dir=docs_dir,
            group_name=group_name,
            group_slug=group_slug,
            model=model,
            timezone=ZoneInfo(timezone),
            llm=llm_config,
            enrichment=enrichment_config,
            cache=cache_config,
            profiles=profiles_config,
            anonymization=AnonymizationConfig(),
            rag=RAGConfig(enabled=enable_rag),
        )

        # Create processor instance
        processor = UnifiedProcessor(config)

        # List groups and exit if requested
        if list_groups:
            self._list_groups_and_exit(processor)
            return

        # Dry run mode
        if dry_run:
            try:
                self._dry_run_and_exit(processor, days_to_process, from_date_obj, to_date_obj)
                return
            except FileNotFoundError as e:
                if debug:
                    raise
                console.print(Panel(
                    f"[red]❌ File not found: {str(e).split(': ')[-1]}[/red]\n\n"
                    "[yellow]Please check that:[/yellow]\n"
                    "• The ZIP file path is correct\n"
                    "• The file exists and is accessible\n"
                    "• You have permission to read the file\n\n"
                    "[bold green]Example:[/bold green]\n"
                    "[cyan]egregora process --zip_files=./whatsapp-export.zip --gemini_key=YOUR_KEY --dry_run[/cyan]\n\n"
                    "[dim]💡 Use --debug=True flag to see detailed error information[/dim]",
                    title="📁 File Error",
                    border_style="red"
                ))
                return
            except Exception as e:
                if debug:
                    raise
                console.print(Panel(
                    f"[red]❌ An error occurred during dry run: {str(e)}[/red]\n\n"
                    "[yellow]This might be due to:[/yellow]\n"
                    "• Invalid ZIP file format\n"
                    "• Corrupted WhatsApp export\n"
                    "• Permission issues\n\n"
                    "[bold green]Try:[/bold green]\n"
                    "• Check your ZIP file is a valid WhatsApp export\n"
                    "• Use [cyan]--debug=True[/cyan] flag for detailed error information\n\n"
                    "[dim]💡 Run with --debug=True to see the full error trace[/dim]",
                    title="⚠️ Dry Run Error",
                    border_style="red"
                ))
                return

        # Process normally
        try:
            self._process_and_display(
                processor,
                days=days_to_process,
                from_date=from_date_obj,
                to_date=to_date_obj,
            )
        except FileNotFoundError as e:
            if debug:
                raise
            console.print(Panel(
                f"[red]❌ File not found: {str(e).split(': ')[-1]}[/red]\n\n"
                "[yellow]Please check that:[/yellow]\n"
                "• The ZIP file path is correct\n"
                "• The file exists and is accessible\n"
                "• You have permission to read the file\n\n"
                "[bold green]Example:[/bold green]\n"
                "[cyan]egregora process --zip_files=./whatsapp-export.zip --gemini_key=YOUR_KEY --output=./my-blog[/cyan]\n\n"
                "[dim]💡 Use --debug=True flag to see detailed error information[/dim]",
                title="📁 File Error",
                border_style="red"
            ))
        except Exception as e:
            if debug:
                raise
            console.print(Panel(
                f"[red]❌ An error occurred: {str(e)}[/red]\n\n"
                "[yellow]This might be due to:[/yellow]\n"
                "• Invalid ZIP file format\n"
                "• Network connectivity issues\n"
                "• API key problems\n"
                "• Insufficient disk space\n\n"
                "[bold green]Try:[/bold green]\n"
                "• Check your ZIP file is a valid WhatsApp export\n"
                "• Verify your API key is correct\n"
                "• Use [cyan]--debug=True[/cyan] flag for detailed error information\n\n"
                "[dim]💡 Run with --debug=True to see the full error trace[/dim]",
                title="⚠️ Processing Error",
                border_style="red"
            ))

    def profiles(
        self,
        action,
        target=None,
        format="pretty",
    ):
        """Manage participant profiles and member information.

        Args:
            action: Action: list, show, generate, clean
            target: Member ID or ZIP path (for generate command)
            format: Output format: pretty, json
        """
        if action not in ["list", "show", "generate", "clean"]:
            console.print(f"❌ Invalid action: {action}. Use: list, show, generate, clean")
            return

        # Build config using CLI arguments
        config = PipelineConfig(
            zip_files=[],
            llm=LLMConfig(),
            enrichment=EnrichmentConfig(),
            cache=CacheConfig(),
            profiles=ProfilesConfig(),
            anonymization=AnonymizationConfig(),
            rag=RAGConfig(),
        )

        if action == "list":
            self._list_profiles(config, format)
        elif action == "show":
            if not target:
                console.print("❌ Specify member ID to show")
                return
            self._show_profile(config, target, format)
        elif action == "generate":
            if not target:
                console.print("❌ Specify ZIP path to generate profiles")
                return
            self._generate_profiles(config, Path(target))
        elif action == "clean":
            self._clean_profiles(config)

    def _list_profiles(self, config: PipelineConfig, output_format: str) -> None:
        """List existing profiles."""
        profiles_dir = config.posts_dir / "profiles" / "json"

        if not profiles_dir.exists():
            console.print("📁 No profiles directory found")
            return

        profile_files = list(profiles_dir.glob("*.json"))

        if not profile_files:
            console.print("👤 No profiles found")
            return

        if output_format == "json":
            profiles_data = []
            for profile_file in profile_files:
                try:
                    with open(profile_file) as f:
                        profile_data = json.load(f)
                        profiles_data.append(
                            {
                                "member_id": profile_file.stem,
                                "name": profile_data.get("name", "Unknown"),
                                "message_count": profile_data.get("message_count", 0),
                                "last_updated": profile_data.get("last_updated", "Unknown"),
                            }
                        )
                except (OSError, json.JSONDecodeError) as e:
                    logging.warning(f"Error reading profile {profile_file}: {e}")
                    continue
            console.print(json.dumps(profiles_data, indent=2, ensure_ascii=False))
        else:
            table = Table(title="👥 Participant Profiles")
            table.add_column("Member ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Messages", style="yellow")
            table.add_column("Last Updated", style="blue")

            for profile_file in profile_files:
                try:
                    with open(profile_file) as f:
                        profile_data = json.load(f)
                        table.add_row(
                            profile_file.stem,
                            profile_data.get("name", "Unknown"),
                            str(profile_data.get("message_count", 0)),
                            profile_data.get("last_updated", "Unknown"),
                        )
                except (OSError, json.JSONDecodeError):
                    table.add_row(profile_file.stem, "❌ Error reading", "-", "-")

            console.print(table)

    def _show_profile(self, config: PipelineConfig, member_id: str, output_format: str) -> None:
        """Show details of a specific profile."""
        profiles_dir = config.posts_dir / "profiles" / "json"
        profile_file = profiles_dir / f"{member_id}.json"

        if not profile_file.exists():
            console.print(f"❌ Profile not found: {member_id}")
            return

        try:
            with open(profile_file) as f:
                profile_data = json.load(f)

            if output_format == "json":
                console.print(json.dumps(profile_data, indent=2, ensure_ascii=False))
            else:
                console.print(
                    Panel(
                        f"[bold]Name:[/bold] {profile_data.get('name', 'Unknown')}\n"
                        f"[bold]Member ID:[/bold] {member_id}\n"
                        f"[bold]Messages:[/bold] {profile_data.get('message_count', 0)}\n"
                        f"[bold]First Activity:[/bold] {profile_data.get('first_seen', 'Unknown')}\n"
                        f"[bold]Last Activity:[/bold] {profile_data.get('last_seen', 'Unknown')}\n"
                        f"[bold]Last Updated:[/bold] {profile_data.get('last_updated', 'Unknown')}\n\n"
                        f"[bold]Description:[/bold]\n{profile_data.get('description', 'No description available')}\n\n"
                        f"[bold]Main Topics:[/bold] {', '.join(profile_data.get('main_topics', []))}\n"
                        f"[bold]Communication Style:[/bold] {profile_data.get('communication_style', 'Unknown')}",
                        title=f"👤 Profile: {profile_data.get('name', member_id)}",
                        border_style="blue",
                    )
                )
        except (OSError, json.JSONDecodeError) as e:
            console.print(f"❌ Error reading profile: {e}")

    def _generate_profiles(self, config: PipelineConfig, zip_path: Path) -> None:
        """Generate profiles from a WhatsApp ZIP."""
        if not zip_path.exists():
            console.print(f"❌ ZIP file not found: {zip_path}")
            return

        console.print(f"👥 Generating profiles from: {zip_path}")

        try:
            console.print("🔄 Processing messages for profile generation...")
            console.print("✅ Profiles would be generated (feature in development)")
            console.print("💡 Use 'egregora process' with real data to generate profiles automatically")

        except Exception as e:
            console.print(f"❌ Error during profile generation: {e}")

    def _clean_profiles(self, config: PipelineConfig) -> None:
        """Remove old or invalid profiles."""
        profiles_dir = config.posts_dir / "profiles" / "json"

        if not profiles_dir.exists():
            console.print("📁 No profiles directory found")
            return

        profile_files = list(profiles_dir.glob("*.json"))
        removed_count = 0

        for profile_file in profile_files:
            try:
                with open(profile_file) as f:
                    json.load(f)  # Validate JSON
            except (OSError, json.JSONDecodeError):
                profile_file.unlink()
                removed_count += 1
                console.print(f"🗑️  Removed corrupted profile: {profile_file.name}")

        if removed_count == 0:
            console.print("✅ All profiles are valid")
        else:
            console.print(f"✅ Removed {removed_count} corrupted profiles")

    # Original helper functions (preserved from the original main function)
    def _list_groups_and_exit(self, processor: UnifiedProcessor) -> None:
        """List discovered groups and exit."""
        sources_to_process, real_groups, virtual_groups = processor._collect_sources()

        console.print(Panel("[bold green]📋 Discovered Groups[/bold green]"))

        if real_groups:
            console.print("\n[bold yellow]📱 Real Groups (from WhatsApp):[/bold yellow]")
            for slug, source in real_groups.items():
                date_range = f"{source.earliest_date} → {source.latest_date}"
                console.print(f"  • {source.name} ({slug}): {date_range}")

        if virtual_groups:
            console.print("\n[bold cyan]🔗 Virtual Groups (merged):[/bold cyan]")
            for slug, config in virtual_groups.items():
                console.print(f"  • {config.name} ({slug}): merges {len(config.source_groups)} groups")

        console.print(f"\n[dim]Total: {len(sources_to_process)} group(s) to process[/dim]")

    def _dry_run_and_exit(
        self,
        processor: UnifiedProcessor,
        days: int | None,
        from_date: date | None,
        to_date: date | None,
    ) -> None:
        """Execute dry run and exit."""
        console.print(
            Panel(
                "[bold blue]🔍 DRY RUN Mode[/bold blue]\nShowing what would be processed without executing",
                border_style="blue",
            )
        )

        plans = processor.plan_runs(days=days, from_date=from_date, to_date=to_date)
        if not plans:
            console.print("[yellow]No groups found with current filters.[/yellow]")
            console.print("Adjust EGREGORA__POSTS_DIR or put exports in data/whatsapp_zips/.\n")
            return

        total_posts = 0
        for plan in plans:
            icon = "📺" if plan.is_virtual else "📝"
            console.print(f"\n[cyan]{icon} {plan.name}[/cyan] ([dim]{plan.slug}[/dim])")
            console.print(f"   Available exports: {plan.export_count}")

            if plan.is_virtual and plan.merges:
                console.print(f"   Combined groups: {', '.join(plan.merges)}")

            if plan.available_dates:
                console.print(
                    f"   Available range: {plan.available_dates[0]} → {plan.available_dates[-1]}"
                )
            else:
                console.print("   No dates available in exports")

            if plan.target_dates:
                if len(plan.target_dates) <= MAX_DATES_TO_SHOW:
                    formatted_dates = ", ".join(str(d) for d in plan.target_dates)
                else:
                    first_5 = ", ".join(str(d) for d in plan.target_dates[:5])
                    last_5 = ", ".join(str(d) for d in plan.target_dates[-5:])
                    formatted_dates = f"{first_5}, ..., {last_5}"
                console.print(f"   Will generate for {len(plan.target_dates)} day(s): {formatted_dates}")
                total_posts += len(plan.target_dates)
            else:
                console.print("   No posts would be generated (no recent data)")

        console.print(f"\nSummary: {len(plans)} group(s) would generate up to {total_posts} post(s).")

        # Show quota estimation
        try:
            quota_info = processor.estimate_api_usage(days=days, from_date=from_date, to_date=to_date)
            console.print("\n📊 API Usage Estimation:")
            console.print(f"   Calls for posts: {quota_info['post_generation_calls']}")
            console.print(f"   Calls for enrichment: {quota_info['enrichment_calls']}")
            console.print(f"   Total calls: {quota_info['total_api_calls']}")
            console.print(
                f"   Estimated time (free tier): {quota_info['estimated_time_minutes']:.1f} minutes"
            )

            if quota_info["total_api_calls"] > QUOTA_WARNING_THRESHOLD:
                console.print(
                    "\n[yellow]⚠️ This operation may exceed Gemini's free quota[/yellow]"
                )
                console.print(
                    "[dim]Free tier: 15 calls/minute. Consider processing in smaller batches.[/dim]"
                )

        except Exception as exc:
            logger.exception("Failed to estimate quota usage")
            console.print(f"\n[yellow]Could not estimate API usage: {exc}[/yellow]")

        console.print()

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
        try:
            quota_info = processor.estimate_api_usage(days=days, from_date=from_date, to_date=to_date)
            if quota_info["total_api_calls"] > QUOTA_WARNING_THRESHOLD_ENRICH:
                console.print(
                    Panel(
                        f"[yellow]⚠️ This operation will make {quota_info['total_api_calls']} API calls[/yellow]\n"
                        f"Estimated time (free tier): {quota_info['estimated_time_minutes']:.1f} minutes\n"
                        f"[dim]Processing may be interrupted by quota limits.[/dim]",
                        border_style="yellow",
                        title="Quota Estimation",
                    )
                )

        except Exception as exc:
            logger.exception("Failed to estimate quota usage before processing")
            console.print(f"\n[yellow]Could not estimate API usage: {exc}[/yellow]")

        console.print()

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


def main():
    """Entry point for the Fire CLI."""
    fire.Fire(EgregoraCLI)


def run():
    """Entry point used by the console script."""
    main()


if __name__ == "__main__":
    main()