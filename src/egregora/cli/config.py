"""Configuration management commands."""

import logging
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from egregora.config.settings import load_egregora_config

console = Console()
logger = logging.getLogger(__name__)

config_app = typer.Typer(
    name="config",
    help="Configuration management and validation",
)


@config_app.command()
def validate(
    site_root: Annotated[
        Path,
        typer.Argument(help="Site root directory containing .egregora/config.yml"),
    ] = Path(),
) -> None:
    """Validate configuration file and show friendly errors.

    Examples:
        egregora config validate
        egregora config validate ./my-blog

    """
    site_root = site_root.expanduser().resolve()
    config_path = site_root / ".egregora" / "config.yml"

    console.print(f"[cyan]Validating configuration at {config_path}[/cyan]\n")

    try:
        config = load_egregora_config(site_root)

        # Show summary of loaded config
        console.print(
            Panel(
                f"[green]✅ Configuration is valid![/green]\n\n"
                f"[cyan]Models:[/cyan]\n"
                f"  Writer: {config.models.writer}\n"
                f"  Enricher: {config.models.enricher}\n"
                f"  Embedding: {config.models.embedding}\n\n"
                f"[cyan]RAG:[/cyan]\n"
                f"  Enabled: {config.rag.enabled}\n"
                f"  Top-K: {config.rag.top_k}\n"
                f"  Min Similarity: {config.rag.min_similarity_threshold}\n\n"
                f"[cyan]Privacy:[/cyan]\n"
                f"  Configured: {bool(config.privacy)}\n\n"
                f"[cyan]Pipeline:[/cyan]\n"
                f"  Step: {config.pipeline.step_size} {config.pipeline.step_unit.value}\n"
                f"  Max Windows: {config.pipeline.max_windows or 'All'}\n"
                f"  Checkpoint: {'Enabled' if config.pipeline.checkpoint_enabled else 'Disabled'}",
                title="✅ Configuration Valid",
                border_style="green",
            )
        )

        # Show warnings if any
        warnings = []

        if config.rag.enabled and not (site_root / config.paths.lancedb_dir).exists():
            warnings.append(f"LanceDB directory does not exist: {config.paths.lancedb_dir}")

        if config.rag.top_k > 20:
            warnings.append(f"RAG top_k={config.rag.top_k} is high. Consider 5-20 for better performance.")

        if config.pipeline.max_prompt_tokens > 200_000:
            warnings.append(
                f"max_prompt_tokens={config.pipeline.max_prompt_tokens} exceeds most model limits. "
                "Consider using --use-full-context-window instead."
            )

        if warnings:
            console.print("\n[yellow]⚠️  Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  • {warning}")

        console.print(f"\n[dim]Loaded from: {config_path}[/dim]")

    except FileNotFoundError:
        console.print(
            Panel(
                f"[yellow]No configuration file found at {config_path}[/yellow]\n\n"
                "Using default configuration. Run 'egregora init' to create a site with config file.",
                title="⚠️  Config Not Found",
                border_style="yellow",
            )
        )

    except ValidationError as e:
        console.print(
            Panel(
                f"[red]Configuration validation failed![/red]\n\n"
                f"Found {len(e.errors())} error(s) in {config_path}",
                title="❌ Validation Failed",
                border_style="red",
            )
        )
        console.print()

        table = Table(title="Configuration Errors", show_header=True)
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Error", style="red")
        table.add_column("Value", style="dim")

        for error in e.errors():
            loc = " → ".join(str(l) for l in error["loc"])
            msg = error["msg"]

            # Try to extract input value if available
            value = error.get("input", "")
            if isinstance(value, dict):
                value = "{...}"
            elif isinstance(value, list):
                value = "[...]"
            else:
                value = str(value)[:50]

            table.add_row(loc, msg, value)

        console.print(table)
        console.print()
        console.print("[dim]Tip: Check YAML syntax and field names match the expected schema[/dim]")
        raise typer.Exit(1)

    except Exception as e:
        console.print(
            Panel(
                f"[red]Error loading configuration:[/red]\n\n{e}",
                title="❌ Load Failed",
                border_style="red",
            )
        )
        logger.exception("Config load failed")
        raise typer.Exit(1)


@config_app.command(name="show")
def show_config(
    site_root: Annotated[
        Path,
        typer.Argument(help="Site root directory containing .egregora/config.yml"),
    ] = Path(),
) -> None:
    """Show current configuration with all settings.

    Examples:
        egregora config show
        egregora config show ./my-blog

    """
    site_root = site_root.expanduser().resolve()
    config_path = site_root / ".egregora" / "config.yml"

    try:
        config = load_egregora_config(site_root)

        # Display as YAML
        import yaml
        from pydantic import BaseModel

        def model_to_dict(model: BaseModel) -> dict:
            """Convert Pydantic model to dict with enums as strings."""
            result = {}
            for field_name, field_value in model:
                if isinstance(field_value, BaseModel):
                    result[field_name] = model_to_dict(field_value)
                elif hasattr(field_value, "value"):  # Enum
                    result[field_name] = field_value.value
                else:
                    result[field_name] = field_value
            return result

        config_dict = model_to_dict(config)
        yaml_output = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

        console.print(
            Panel(
                f"[cyan]{yaml_output}[/cyan]",
                title=f"Configuration: {config_path}",
                border_style="cyan",
            )
        )

    except FileNotFoundError:
        console.print(f"[yellow]No configuration file found at {config_path}[/yellow]")
        console.print("Run 'egregora init' to create a site with default configuration.")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)
