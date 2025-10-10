"""Rich Typer-based command line interface for Egregora."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import PipelineConfig

from .processor import UnifiedProcessor

app = typer.Typer(
    name="egregora",
    help="🗣️ Gera posts diárias a partir de exports do WhatsApp.",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()


def _validate_config_file(value: Path | None) -> Path | None:
    """Ensure the provided configuration file exists."""

    if value and not value.exists():
        raise typer.BadParameter(f"Arquivo de configuração não encontrado: {value}")
    return value


def _parse_timezone(value: str | None) -> ZoneInfo | None:
    """Parse timezone strings into :class:`ZoneInfo` objects."""

    if not value:
        return None

    try:
        return ZoneInfo(value)
    except Exception as exc:  # pragma: no cover - defensive on ZoneInfo
        raise typer.BadParameter(f"Timezone '{value}' não é válido: {exc}") from exc


ConfigFileOption = Annotated[
    Path | None,
    typer.Option(
        "--config", "-c", callback=_validate_config_file, help="Arquivo TOML de configuração."
    ),
]
ZipsDirOption = Annotated[
    Path | None,
    typer.Option(
        help="Diretório com exports .zip do WhatsApp (nomes naturais ou com prefixo YYYY-MM-DD)."
    ),
]
PostsDirOption = Annotated[
    Path | None,
    typer.Option(help="Diretório onde as posts serão escritas."),
]
ModelOption = Annotated[
    str | None,
    typer.Option(help="Nome do modelo Gemini a ser usado."),
]
TimezoneOption = Annotated[
    str | None,
    typer.Option(help="Timezone IANA (ex.: America/Porto_Velho) usado para marcar a data de hoje."),
]
DaysOption = Annotated[
    int,
    typer.Option(min=1, help="Quantidade de dias mais recentes a incluir no prompt."),
]
DisableEnrichmentOption = Annotated[
    bool,
    typer.Option(
        "--disable-enrichment",
        "--no-enrich",
        help="Desativa o enriquecimento de conteúdos compartilhados.",
    ),
]
DisableCacheOption = Annotated[
    bool,
    typer.Option("--no-cache", help="Desativa o cache persistente de enriquecimento."),
]
ListGroupsOption = Annotated[
    bool,
    typer.Option("--list", "-l", help="Lista grupos descobertos e sai."),
]
DryRunOption = Annotated[
    bool,
    typer.Option("--dry-run", help="Simula a execução e mostra quais posts seriam geradas."),
]


def _build_pipeline_config(  # noqa: PLR0913
    *,
    config_file: Path | None = None,
    zips_dir: Path | None = None,
    posts_dir: Path | None = None,
    model: str | None = None,
    timezone: str | None = None,
    disable_enrichment: bool = False,
    disable_cache: bool = False,
) -> PipelineConfig:
    """Carrega ou monta um :class:`PipelineConfig` a partir das opções da CLI."""

    timezone_override = _parse_timezone(timezone)

    if config_file:
        try:
            config = PipelineConfig.load(toml_path=config_file)
        except Exception as exc:  # pragma: no cover - configuration validation
            console.print(f"[red]❌ Não foi possível carregar o arquivo TOML:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    else:
        config = PipelineConfig.with_defaults(
            zips_dir=zips_dir,
            posts_dir=posts_dir,
            model=model,
            timezone=timezone_override,
        )

    if zips_dir:
        config.zips_dir = zips_dir
    if posts_dir:
        config.posts_dir = posts_dir
    if model:
        config.model = model
    if timezone_override:
        config.timezone = timezone_override

    if disable_enrichment:
        config.enrichment.enabled = False
    if disable_cache:
        config.cache.enabled = False

    return config


def _process_command(  # noqa: PLR0913
    *,
    config_file: Path | None = None,
    zips_dir: Path | None = None,
    posts_dir: Path | None = None,
    model: str | None = None,
    timezone: str | None = None,
    days: int = 2,
    disable_enrichment: bool = False,
    disable_cache: bool = False,
    list_groups: bool = False,
    dry_run: bool = False,
) -> None:
    """Executa o fluxo de processamento com as opções fornecidas."""

    config = _build_pipeline_config(
        config_file=config_file,
        zips_dir=zips_dir,
        posts_dir=posts_dir,
        model=model,
        timezone=timezone,
        disable_enrichment=disable_enrichment,
        disable_cache=disable_cache,
    )

    processor = UnifiedProcessor(config)

    if list_groups:
        _show_groups_table(processor)
        raise typer.Exit()

    if dry_run:
        _show_dry_run(processor, days)
        raise typer.Exit()

    _process_and_display(processor, days)


@app.command()
def process(  # noqa: PLR0913
    config_file: ConfigFileOption = None,
    zips_dir: ZipsDirOption = None,
    posts_dir: PostsDirOption = None,
    model: ModelOption = None,
    timezone: TimezoneOption = None,
    days: DaysOption = 2,
    disable_enrichment: DisableEnrichmentOption = False,
    disable_cache: DisableCacheOption = False,
    list_groups: ListGroupsOption = False,
    dry_run: DryRunOption = False,
) -> None:
    """Processa grupos do WhatsApp e gera posts diárias."""

    _process_command(
        config_file=config_file,
        zips_dir=zips_dir,
        posts_dir=posts_dir,
        model=model,
        timezone=timezone,
        days=days,
        disable_enrichment=disable_enrichment,
        disable_cache=disable_cache,
        list_groups=list_groups,
        dry_run=dry_run,
    )


@app.callback(invoke_without_command=True)
def main(  # noqa: PLR0913
    ctx: typer.Context,
    config_file: ConfigFileOption = None,
    zips_dir: ZipsDirOption = None,
    posts_dir: PostsDirOption = None,
    model: ModelOption = None,
    timezone: TimezoneOption = None,
    days: DaysOption = 2,
    disable_enrichment: DisableEnrichmentOption = False,
    disable_cache: DisableCacheOption = False,
    list_groups: ListGroupsOption = False,
    dry_run: DryRunOption = False,
) -> None:
    """Permite que o comando padrão execute o processamento sem subcomando explícito."""

    if ctx.invoked_subcommand is not None:
        return

    _process_command(
        config_file=config_file,
        zips_dir=zips_dir,
        posts_dir=posts_dir,
        model=model,
        timezone=timezone,
        days=days,
        disable_enrichment=disable_enrichment,
        disable_cache=disable_cache,
        list_groups=list_groups,
        dry_run=dry_run,
    )





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

    app()


if __name__ == "__main__":
    run()
