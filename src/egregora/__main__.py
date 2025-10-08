"""Rich Typer-based command line interface for Egregora."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import PipelineConfig
from .discover import discover_identifier
from .processor import UnifiedProcessor
from .remote_sync import sync_remote_source_config

app = typer.Typer(
    name="egregora",
    help="🗣️ Gera posts diárias a partir de exports do WhatsApp.",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()


def _validate_config_file(value: Optional[Path]) -> Optional[Path]:
    """Ensure the provided configuration file exists."""

    if value and not value.exists():
        raise typer.BadParameter(f"Arquivo de configuração não encontrado: {value}")
    return value


def _parse_timezone(value: Optional[str]) -> Optional[ZoneInfo]:
    """Parse timezone strings into :class:`ZoneInfo` objects."""

    if not value:
        return None

    try:
        return ZoneInfo(value)
    except Exception as exc:  # pragma: no cover - defensive on ZoneInfo
        raise typer.BadParameter(f"Timezone '{value}' não é válido: {exc}") from exc


ConfigFileOption = Annotated[
    Optional[Path],
    typer.Option("--config", "-c", callback=_validate_config_file, help="Arquivo TOML de configuração."),
]
ZipsDirOption = Annotated[
    Optional[Path],
    typer.Option(help="Diretório com exports .zip do WhatsApp (nomes naturais ou com prefixo YYYY-MM-DD)."),
]
PostsDirOption = Annotated[
    Optional[Path],
    typer.Option(help="Diretório onde as posts serão escritas."),
]
ModelOption = Annotated[
    Optional[str],
    typer.Option(help="Nome do modelo Gemini a ser usado."),
]
RemoteUrlOption = Annotated[
    Optional[str],
    typer.Option(
        "--remote-url",
        help="URL do Google Drive com exports .zip para sincronizar automaticamente.",
    ),
]
TimezoneOption = Annotated[
    Optional[str],
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


def _build_pipeline_config(
    *,
    config_file: Optional[Path] = None,
    zips_dir: Optional[Path] = None,
    posts_dir: Optional[Path] = None,
    model: Optional[str] = None,
    remote_url: Optional[str] = None,
    timezone: Optional[str] = None,
    disable_enrichment: bool = False,
    disable_cache: bool = False,
) -> PipelineConfig:
    """Carrega ou monta um :class:`PipelineConfig` a partir das opções da CLI."""

    timezone_override = _parse_timezone(timezone)

    remote_url_value = remote_url.strip() if remote_url else None

    if config_file:
        try:
            config = PipelineConfig.from_toml(config_file)
        except Exception as exc:  # pragma: no cover - configuration validation
            console.print(f"[red]❌ Não foi possível carregar o arquivo TOML:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        if remote_url_value:
            config.remote_source.gdrive_url = remote_url_value
    else:
        config = PipelineConfig.with_defaults(
            zips_dir=zips_dir,
            posts_dir=posts_dir,
            model=model,
            timezone=timezone_override,
            remote_source={"gdrive_url": remote_url_value} if remote_url_value else None,
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


def _process_command(
    *,
    config_file: Optional[Path] = None,
    zips_dir: Optional[Path] = None,
    posts_dir: Optional[Path] = None,
    model: Optional[str] = None,
    remote_url: Optional[str] = None,
    timezone: Optional[str] = None,
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
        remote_url=remote_url,
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


@app.command("sync")
def sync_command(
    config_file: ConfigFileOption = None,
    zips_dir: ZipsDirOption = None,
    posts_dir: PostsDirOption = None,
    model: ModelOption = None,
    timezone: TimezoneOption = None,
    disable_enrichment: DisableEnrichmentOption = False,
    disable_cache: DisableCacheOption = False,
) -> None:
    """Baixa exports do WhatsApp da fonte remota configurada."""

    config = _build_pipeline_config(
        config_file=config_file,
        zips_dir=zips_dir,
        posts_dir=posts_dir,
        model=model,
        timezone=timezone,
        disable_enrichment=disable_enrichment,
        disable_cache=disable_cache,
    )

    console.print(
        Panel(
            f"[bold]Diretório de destino:[/bold] {config.zips_dir.resolve()}",
            title="☁️ Sincronização Remota",
            border_style="cyan",
        )
    )

    outcome = sync_remote_source_config(config)

    if not outcome.attempted:
        console.print(
            Panel(
                "Nenhuma URL remota configurada. Atualize o TOML ou variáveis de ambiente.",
                border_style="yellow",
            )
        )
        raise typer.Exit(code=1)

    if outcome.error:
        console.print(
            Panel(
                f"[red]Falha ao sincronizar exports:[/red] {outcome.error}",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    summary_panel = Panel(
        f"Foram sincronizados [bold]{len(outcome.new_archives)}[/bold] arquivo(s) novo(s).",
        border_style="green" if outcome.new_archives else "blue",
    )
    console.print(summary_panel)

    if outcome.new_archives:
        table = Table(
            title="📦 Arquivos novos",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Arquivo", style="green")

        base = config.zips_dir.resolve()
        for path in outcome.new_archives:
            try:
                rel = path.relative_to(base)
            except ValueError:
                rel = path
            table.add_row(str(rel))

        console.print(table)

    console.print(
        Panel(
            f"Total de arquivos disponíveis: [bold]{len(outcome.all_archives)}[/bold]",
            border_style="magenta",
        )
    )


@app.command()
def process(
    config_file: ConfigFileOption = None,
    zips_dir: ZipsDirOption = None,
    posts_dir: PostsDirOption = None,
    model: ModelOption = None,
    remote_url: RemoteUrlOption = None,
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
        remote_url=remote_url,
        timezone=timezone,
        days=days,
        disable_enrichment=disable_enrichment,
        disable_cache=disable_cache,
        list_groups=list_groups,
        dry_run=dry_run,
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config_file: ConfigFileOption = None,
    zips_dir: ZipsDirOption = None,
    posts_dir: PostsDirOption = None,
    model: ModelOption = None,
    remote_url: RemoteUrlOption = None,
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
        remote_url=remote_url,
        timezone=timezone,
        days=days,
        disable_enrichment=disable_enrichment,
        disable_cache=disable_cache,
        list_groups=list_groups,
        dry_run=dry_run,
    )


@app.command()
def discover(
    value: Annotated[
        str,
        typer.Argument(help="Telefone ou apelido a ser anonimizado."),
    ],
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Formato preferido ao exibir o resultado (human, short, full).",
        ),
    ] = "human",
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Imprime apenas o identificador no formato escolhido."),
    ] = False,
) -> None:
    """Calcula o identificador anônimo para um telefone ou apelido."""

    try:
        result = discover_identifier(value)
    except ValueError as exc:
        console.print(f"[red]❌ Erro:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    fmt = output_format.lower()
    selected = result.get(fmt)
    if not selected:
        console.print(f"[red]❌ Formato desconhecido:[/red] {output_format}")
        raise typer.Exit(code=1)

    if quiet:
        console.print(selected)
        raise typer.Exit()

    panel = Panel(
        f"[bold cyan]{selected}[/bold cyan]",
        title=f"🔐 Identificador Anônimo ({fmt})",
        border_style="cyan",
    )
    console.print(panel)

    table = Table(title="Formatos Disponíveis", show_header=True, header_style="bold magenta")
    table.add_column("Formato", style="cyan")
    table.add_column("Identificador", style="green")

    for key in ("human", "short", "full"):
        identifier = result.variants.get(key, "")
        table.add_row(key, identifier)

    console.print(table)
    console.print(
        Panel(
            f"[bold]Entrada original:[/bold] {result.raw_input}\n"
            f"[bold]Tipo detectado:[/bold] {result.detected_type}\n"
            f"[bold]Normalizado:[/bold] {result.normalized}",
            border_style="magenta",
        )
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
