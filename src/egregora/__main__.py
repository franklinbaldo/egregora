"""Simplified command line interface for Egregora."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import PipelineConfig
from .processor import UnifiedProcessor

console = Console()


def main(  # noqa: PLR0913
    zip_files: list[Path] = typer.Argument(..., help="Um ou mais arquivos .zip do WhatsApp para processar"),
    config_file: Path = typer.Option(None, "--config", "-c", help="Arquivo TOML de configuração"),
    output_dir: Path = typer.Option(None, "--output", "-o", help="Diretório onde as posts serão escritas"),
    group_name: str = typer.Option(None, "--group-name", help="Nome do grupo (auto-detectado se não fornecido)"),
    group_slug: str = typer.Option(None, "--group-slug", help="Slug do grupo (auto-gerado se não fornecido)"),
    model: str = typer.Option(None, "--model", help="Nome do modelo Gemini a ser usado"),
    timezone: str = typer.Option(None, "--timezone", help="Timezone IANA (ex.: America/Porto_Velho)"),
    days: int = typer.Option(2, "--days", min=1, help="Quantidade de dias mais recentes a incluir no prompt"),
    disable_enrichment: bool = typer.Option(False, "--disable-enrichment", "--no-enrich", help="Desativa o enriquecimento"),
    disable_cache: bool = typer.Option(False, "--no-cache", help="Desativa o cache persistente"),
    list_groups: bool = typer.Option(False, "--list", "-l", help="Lista grupos descobertos e sai"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula a execução e mostra quais posts seriam geradas"),
) -> None:
    """Processa um ou mais arquivos .zip do WhatsApp e gera posts diárias."""
    
    # Validate config file
    if config_file and not config_file.exists():
        console.print(f"[red]❌ Arquivo de configuração não encontrado: {config_file}[/red]")
        raise typer.Exit(code=1)
    
    # Parse timezone
    timezone_override = None
    if timezone:
        try:
            timezone_override = ZoneInfo(timezone)
        except Exception as exc:
            console.print(f"[red]❌ Timezone '{timezone}' não é válido: {exc}[/red]")
            raise typer.Exit(code=1)

    # Build configuration
    if config_file:
        try:
            config = PipelineConfig.load(toml_path=config_file)
        except Exception as exc:
            console.print(f"[red]❌ Não foi possível carregar o arquivo TOML:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    else:
        config = PipelineConfig.with_defaults(
            zip_files=zip_files,
            output_dir=output_dir,
            group_name=group_name,
            group_slug=group_slug,
            model=model,
            timezone=timezone_override,
        )

    # Override with CLI parameters  
    config.zip_files = zip_files
    if output_dir:
        config.posts_dir = output_dir
    if group_name:
        config.group_name = group_name
    if group_slug:
        config.group_slug = group_slug
    if model:
        config.model = model
    if timezone_override:
        config.timezone = timezone_override

    if disable_enrichment:
        config.enrichment.enabled = False
    if disable_cache:
        config.cache.enabled = False

    # Create processor
    processor = UnifiedProcessor(config)

    # Handle special modes
    if list_groups:
        _show_groups_table(processor)
        raise typer.Exit()

    if dry_run:
        _show_dry_run(processor, days)
        raise typer.Exit()

    # Process normally
    _process_and_display(processor, days)







def _show_groups_table(processor: UnifiedProcessor) -> None:
    """Mostra grupos descobertos em tabela formatada."""

    groups = processor.list_groups()
    if not groups:
        console.print("[yellow]Nenhum grupo foi encontrado.[/yellow]")
        return

    table = Table(
        title="📁 Grupos Descobertos",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Tipo", style="cyan", width=10)
    table.add_column("Nome", style="white")
    table.add_column("Slug", style="dim")
    table.add_column("Exports", justify="right", style="green")
    table.add_column("Período", style="yellow")

    for slug, info in sorted(groups.items()):
        tipo_icon = "📺 Virtual" if info["type"] == "virtual" else "📝 Real"
        periodo = f"{info['date_range'][0]} → {info['date_range'][1]}"
        table.add_row(
            tipo_icon,
            info["name"],
            slug,
            str(info["export_count"]),
            periodo,
        )

    console.print(table)

    extra_notes: list[str] = []
    for slug, info in sorted(groups.items()):
        if info["type"] == "real" and info["in_virtual"]:
            extra_notes.append(
                f"[dim]• {slug} faz parte dos grupos virtuais: {', '.join(info['in_virtual'])}[/dim]"
            )
        elif info["type"] == "virtual" and info.get("merges"):
            extra_notes.append(
                f"[dim]• {slug} combina os exports: {', '.join(info['merges'])}[/dim]"
            )

    if extra_notes:
        console.print("\n".join(extra_notes))


def _show_dry_run(processor: UnifiedProcessor, days: int) -> None:
    """Mostra preview do que seria processado."""

    console.print(
        Panel(
            "[bold yellow]🔍 Modo DRY RUN[/bold yellow]\n"
            "Mostrando o que seria processado sem executar",
            border_style="yellow",
        )
    )

    plans = processor.plan_runs(days=days)
    if not plans:
        console.print("[yellow]Nenhum grupo foi encontrado com os filtros atuais.[/yellow]")
        console.print("Use --config ou ajuste diretórios para apontar para os exports corretos.\n")
        return

    total_posts = 0
    for plan in plans:
        icon = "📺" if plan.is_virtual else "📝"
        console.print(f"\n[cyan]{icon} {plan.name}[/cyan] ([dim]{plan.slug}[/dim])")
        console.print(f"   Exports disponíveis: {plan.export_count}")

        if plan.is_virtual and plan.merges:
            console.print(f"   Grupos combinados: {', '.join(plan.merges)}")

        if plan.available_dates:
            console.print(
                f"   Intervalo disponível: {plan.available_dates[0]} → {plan.available_dates[-1]}"
            )
        else:
            console.print("   Nenhuma data disponível nos exports")

        if plan.target_dates:
            formatted_dates = ", ".join(str(d) for d in plan.target_dates)
            console.print(
                f"   Será gerado para {len(plan.target_dates)} dia(s): [green]{formatted_dates}[/green]"
            )
            total_posts += len(plan.target_dates)
        else:
            console.print("   Nenhuma post seria gerada (sem dados recentes)")

    console.print(
        f"\n[bold]Resumo:[/bold] {len(plans)} grupo(s) gerariam até {total_posts} post(s).\n"
    )


def _process_and_display(processor: UnifiedProcessor, days: int) -> None:
    """Processa grupos e mostra resultado formatado."""

    console.print(Panel("[bold green]🚀 Processando Grupos[/bold green]", border_style="green"))

    results = processor.process_all(days=days)

    total = sum(len(v) for v in results.values())
    table = Table(
        title="✅ Processamento Completo",
        show_header=True,
        header_style="bold green",
    )
    table.add_column("Grupo", style="cyan")
    table.add_column("Posts", justify="right", style="green")

    for slug, posts in sorted(results.items()):
        table.add_row(slug, str(len(posts)))

    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", style="bold")

    console.print(table)


def run() -> None:
    """Entry point used by the console script."""
    typer.run(main)


if __name__ == "__main__":
    run()
