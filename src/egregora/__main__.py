"""Enhanced command line interface for Egregora with subcommands."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import PipelineConfig
from .processor import UnifiedProcessor

console = Console()
app = typer.Typer(help="Egregora - WhatsApp to post pipeline with AI enrichment")


@app.command("process")
def process_command(  # noqa: PLR0913
    zip_files: list[Path] = typer.Argument(
        ..., help="Um ou mais arquivos .zip do WhatsApp para processar"
    ),
    output_dir: Path = typer.Option(
        None, "--output", "-o", help="Diretório onde as posts serão escritas"
    ),
    group_name: str = typer.Option(
        None, "--group-name", help="Nome do grupo (auto-detectado se não fornecido)"
    ),
    group_slug: str = typer.Option(
        None, "--group-slug", help="Slug do grupo (auto-gerado se não fornecido)"
    ),
    model: str = typer.Option(
        "gemini-flash-lite-latest", "--model", help="Nome do modelo Gemini a ser usado"
    ),
    timezone: str = typer.Option("America/Porto_Velho", "--timezone", help="Timezone IANA"),
    days: int = typer.Option(
        None,
        "--days",
        min=1,
        help="Processar os N dias mais recentes. Incompatível com --from/--to.",
    ),
    from_date: str = typer.Option(
        None,
        "--from-date",
        help="Data de início (YYYY-MM-DD). Incompatível com --days.",
        formats=["%Y-%m-%d"],
    ),
    to_date: str = typer.Option(
        None,
        "--to-date",
        help="Data de fim (YYYY-MM-DD). Incompatível com --days.",
        formats=["%Y-%m-%d"],
    ),
    disable_enrichment: bool = typer.Option(
        False, "--disable-enrichment", "--no-enrich", help="Desativa o enriquecimento"
    ),
    disable_cache: bool = typer.Option(False, "--no-cache", help="Desativa o cache persistente"),
    list_groups: bool = typer.Option(False, "--list", "-l", help="Lista grupos descobertos e sai"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simula a execução e mostra quais posts seriam geradas"
    ),
    # Profile linking options
    link_member_profiles: bool = typer.Option(
        True, "--link-profiles/--no-link-profiles", help="Link member mentions to profile pages"
    ),
    profile_base_url: str = typer.Option(
        "/profiles/", "--profile-base-url", help="Base URL for profile links"
    ),
    # LLM options
    safety_threshold: str = typer.Option(
        "BLOCK_NONE", "--safety-threshold", help="Gemini safety threshold"
    ),
    thinking_budget: int = typer.Option(
        -1, "--thinking-budget", help="Gemini thinking budget (-1 for unlimited)"
    ),
    # Enrichment options
    max_links: int = typer.Option(50, "--max-links", help="Maximum links to enrich per post"),
    relevance_threshold: int = typer.Option(
        2, "--relevance-threshold", help="Minimum relevance threshold for enrichment"
    ),
    # Cache options
    cache_dir: str = typer.Option("cache", "--cache-dir", help="Cache directory path"),
    auto_cleanup_days: int = typer.Option(
        90, "--auto-cleanup-days", help="Auto cleanup cache after N days"
    ),
) -> None:
    """Processa um ou mais arquivos .zip do WhatsApp e gera posts diárias."""

    # Configuration now uses only CLI arguments

    # Mutual exclusivity validation
    date_options_count = sum([days is not None, from_date is not None, to_date is not None])
    if days is not None and (from_date is not None or to_date is not None):
        console.print("❌ A opção --days não pode ser usada com --from-date ou --to-date.")
        raise typer.Exit(1)

    # Date parsing and validation
    from_date_obj = None
    to_date_obj = None

    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        except ValueError:
            console.print(f"❌ Data de início inválida: '{from_date}'. Use YYYY-MM-DD.")
            raise typer.Exit(1)

    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
        except ValueError:
            console.print(f"❌ Data de fim inválida: '{to_date}'. Use YYYY-MM-DD.")
            raise typer.Exit(1)

    # Date range validation
    if from_date_obj and to_date_obj and from_date_obj > to_date_obj:
        console.print("❌ Data de início deve ser anterior à data de fim.")
        raise typer.Exit(1)

    # Convert days to days_to_process for backward compatibility
    days_to_process = days

    # Build configuration using CLI arguments only
    from pathlib import Path

    from .config import (
        AnonymizationConfig,
        CacheConfig,
        EnrichmentConfig,
        LLMConfig,
        PipelineConfig,
        ProfilesConfig,
    )
    from .rag.config import RAGConfig

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

    # Build main configuration
    config = PipelineConfig(
        zip_files=zip_files,
        posts_dir=Path(output_dir) if output_dir else Path("data"),
        group_name=group_name,
        group_slug=group_slug,
        model=model,
        timezone=ZoneInfo(timezone),
        llm=llm_config,
        enrichment=enrichment_config,
        cache=cache_config,
        profiles=profiles_config,
        anonymization=AnonymizationConfig(),
        rag=RAGConfig(),
    )

    # Configuration is now fully built from CLI arguments above

    # Create processor instance
    processor = UnifiedProcessor(config)

    # List groups and exit if requested
    if list_groups:
        _list_groups_and_exit(processor)

    # Dry run mode
    if dry_run:
        _dry_run_and_exit(processor, days_to_process, from_date_obj, to_date_obj)

    # Process normally
    _process_and_display(
        processor,
        days=days_to_process,
        from_date=from_date_obj,
        to_date=to_date_obj,
    )


@app.command("enrich")
def enrich_command(
    url: str = typer.Argument(..., help="URL ou caminho de mídia para enriquecer"),
    config_file: Path = typer.Option(
        None, "--config", "-c", help="[DEPRECATED] Use environment variables instead"
    ),
    model: str = typer.Option(None, "--model", help="Modelo Gemini para enriquecimento"),
    output_format: str = typer.Option(
        "pretty", "--format", "-f", help="Formato de saída: pretty, json"
    ),
    save_cache: bool = typer.Option(True, "--cache/--no-cache", help="Salvar resultado no cache"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simula enriquecimento sem chamadas da API"
    ),
) -> None:
    """Testa o enriquecimento de uma URL ou mídia específica."""

    console.print(f"🔍 Testando enriquecimento: {url}")

    if dry_run:
        console.print("🔍 Modo DRY RUN - Simulando enriquecimento")
        # Show what would be done without API calls
        if url.startswith(("http://", "https://")):
            console.print(
                Panel(
                    f"[bold blue]📡 URL Enriquecimento (Simulado)[/bold blue]\n\n"
                    f"[bold]URL:[/bold] {url}\n"
                    f"[bold]Tipo:[/bold] Link da web\n"
                    f"[bold]Análise:[/bold] Extrairia conteúdo, palavras-chave e resumo\n"
                    f"[bold]APIs:[/bold] Gemini (content analysis)\n"
                    f"[bold]Cache:[/bold] {'Habilitado' if save_cache else 'Desabilitado'}",
                    title="Simulação de Enriquecimento",
                    border_style="blue",
                )
            )
        else:
            media_path = Path(url)
            if media_path.exists():
                console.print(
                    Panel(
                        f"[bold blue]🖼️ Mídia Enriquecimento (Simulado)[/bold blue]\n\n"
                        f"[bold]Arquivo:[/bold] {media_path.name}\n"
                        f"[bold]Tipo:[/bold] {media_path.suffix or 'Desconhecido'}\n"
                        f"[bold]Análise:[/bold] Análise de conteúdo visual/áudio\n"
                        f"[bold]APIs:[/bold] Gemini (multimodal analysis)\n"
                        f"[bold]Cache:[/bold] {'Habilitado' if save_cache else 'Desabilitado'}",
                        title="Simulação de Enriquecimento",
                        border_style="blue",
                    )
                )
            else:
                console.print(f"❌ Arquivo não encontrado: {media_path}")
                raise typer.Exit(1)
        return

    try:
        # Import here to avoid dependency issues
        from .enrichment import ContentEnricher
        from .gemini_manager import GeminiManager

        # Build minimal config using CLI arguments
        if config_file:
            console.print(
                "[red]❌ Configuration files are no longer supported. Use CLI arguments instead.[/red]"
            )
            raise typer.Exit(code=1)

        from .config import (
            AnonymizationConfig,
            CacheConfig,
            EnrichmentConfig,
            LLMConfig,
            PipelineConfig,
            ProfilesConfig,
        )
        from .rag.config import RAGConfig

        config = PipelineConfig(
            zip_files=[],  # Not needed for enrichment testing
            model=model or "gemini-flash-lite-latest",
            llm=LLMConfig(),
            enrichment=EnrichmentConfig(),
            cache=CacheConfig(),
            profiles=ProfilesConfig(),
            anonymization=AnonymizationConfig(),
            rag=RAGConfig(),
        )

        # Create enricher
        gemini_manager = GeminiManager()
        enricher = ContentEnricher(config.enrichment, gemini_manager=gemini_manager)

        # Test if it's a URL or file path
        if url.startswith(("http://", "https://")):
            # It's a URL - create a minimal DataFrame for testing
            console.print(f"📡 Enriquecendo URL: {url}")

            # Create a minimal polars DataFrame with the URL in a message
            from datetime import datetime

            import polars as pl

            test_df = pl.DataFrame(
                {
                    "timestamp": [datetime.now()],
                    "sender": ["Test-User"],
                    "message": [f"Confira este link: {url}"],
                    "date": [datetime.now().date()],
                }
            )

            # Run enrichment on the DataFrame
            result = asyncio.run(enricher.enrich_dataframe(test_df, client=gemini_manager.client))

        else:
            # It's likely a file path
            media_path = Path(url)
            if not media_path.exists():
                console.print(f"❌ Arquivo não encontrado: {media_path}")
                raise typer.Exit(1)

            console.print(f"🖼️ Enriquecendo mídia: {media_path}")

            # Create a minimal DataFrame with media reference
            from datetime import datetime

            import polars as pl

            test_df = pl.DataFrame(
                {
                    "timestamp": [datetime.now()],
                    "sender": ["Test-User"],
                    "message": [f"<Mídia oculta> {media_path.name}"],
                    "date": [datetime.now().date()],
                }
            )

            result = asyncio.run(enricher.enrich_dataframe(test_df, client=gemini_manager.client))

        # Format output
        if output_format == "json":
            # Convert result to dict for JSON output
            metrics_dict = {}
            if result.metrics:
                metrics_dict = {
                    "started_at": result.metrics.started_at.isoformat(),
                    "finished_at": result.metrics.finished_at.isoformat(),
                    "total_references": result.metrics.total_references,
                    "analyzed_items": result.metrics.analyzed_items,
                    "relevant_items": result.metrics.relevant_items,
                    "error_count": result.metrics.error_count,
                    "domains": result.metrics.domains,
                    "threshold": result.metrics.threshold,
                }

            result_dict = {
                "items_count": len(result.items),
                "errors_count": len(result.errors),
                "duration_seconds": result.duration_seconds,
                "metrics": metrics_dict,
                "errors": result.errors if result.errors else [],
            }
            console.print(json.dumps(result_dict, indent=2, ensure_ascii=False))
        else:
            # Pretty format
            relevant_items = result.relevant_items(2) if result.items else []
            console.print(
                Panel(
                    f"[bold green]✅ Enriquecimento concluído[/bold green]\n\n"
                    f"[bold]Itens processados:[/bold] {len(result.items)}\n"
                    f"[bold]Itens relevantes:[/bold] {len(relevant_items)}\n"
                    f"[bold]Erros:[/bold] {len(result.errors)}\n"
                    f"[bold]Duração:[/bold] {result.duration_seconds:.2f}s",
                    title="Resultado do Enriquecimento",
                    border_style="green" if not result.errors else "yellow",
                )
            )

            if result.errors:
                console.print("\n[bold red]❌ Erros encontrados:[/bold red]")
                for error in result.errors[:3]:  # Show first 3
                    console.print(f"  • {error}")
                if len(result.errors) > 3:
                    console.print(f"  ... e mais {len(result.errors) - 3}")

            if relevant_items:
                console.print("\n[bold yellow]📋 Itens relevantes:[/bold yellow]")
                for item in relevant_items:  # Show all items
                    ref = item.reference
                    analysis = item.analysis
                    console.print(f"  • {ref.url}")
                    if analysis and analysis.summary:
                        console.print(f"    {analysis.summary}")
                    if analysis and analysis.topics:
                        console.print(f"    [bold]Tópicos:[/bold] {', '.join(analysis.topics)}")
                    if analysis and analysis.actions:
                        console.print("    [bold]Ações:[/bold]")
                        for action in analysis.actions:
                            console.print(f"      - {action.description}")
                    if analysis:
                        console.print(f"    [bold]Relevância:[/bold] {analysis.relevance}/5")
                    console.print()  # Add spacing between items

    except ImportError as e:
        console.print(f"❌ Dependência não encontrada: {e}")
        console.print("💡 Instale as dependências: uv sync")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Erro durante enriquecimento: {e}")
        raise typer.Exit(1)


@app.command("profiles")
def profiles_command(
    action: str = typer.Argument(..., help="Ação: list, show, generate, clean"),
    target: str = typer.Argument(None, help="ID do membro ou caminho do ZIP (para generate)"),
    config_file: Path = typer.Option(
        None, "--config", "-c", help="[DEPRECATED] Use environment variables instead"
    ),
    output_format: str = typer.Option("pretty", "--format", "-f", help="Formato: pretty, json"),
) -> None:
    """Gerencia perfis de participantes."""

    if action not in ["list", "show", "generate", "clean"]:
        console.print(f"❌ Ação inválida: {action}. Use: list, show, generate, clean")
        raise typer.Exit(1)

    # Build config using CLI arguments
    if config_file:
        console.print(
            "[red]❌ Configuration files are no longer supported. Use CLI arguments instead.[/red]"
        )
        raise typer.Exit(code=1)

    from .config import (
        AnonymizationConfig,
        CacheConfig,
        EnrichmentConfig,
        LLMConfig,
        PipelineConfig,
        ProfilesConfig,
    )
    from .rag.config import RAGConfig

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
        _list_profiles(config, output_format)
    elif action == "show":
        if not target:
            console.print("❌ Especifique o ID do membro para mostrar")
            raise typer.Exit(1)
        _show_profile(config, target, output_format)
    elif action == "generate":
        if not target:
            console.print("❌ Especifique o caminho do ZIP para gerar perfis")
            raise typer.Exit(1)
        _generate_profiles(config, Path(target))
    elif action == "clean":
        _clean_profiles(config)


def _list_profiles(config: PipelineConfig, output_format: str) -> None:
    """Lista perfis existentes."""
    profiles_dir = config.posts_dir / "profiles" / "json"

    if not profiles_dir.exists():
        console.print("📁 Nenhum diretório de perfis encontrado")
        return

    profile_files = list(profiles_dir.glob("*.json"))

    if not profile_files:
        console.print("👤 Nenhum perfil encontrado")
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
            except Exception:
                continue
        console.print(json.dumps(profiles_data, indent=2, ensure_ascii=False))
    else:
        table = Table(title="👥 Perfis de Participantes")
        table.add_column("ID do Membro", style="cyan")
        table.add_column("Nome", style="green")
        table.add_column("Mensagens", style="yellow")
        table.add_column("Última Atualização", style="blue")

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
            except Exception:
                table.add_row(profile_file.stem, "❌ Erro ao ler", "-", "-")

        console.print(table)


def _show_profile(config: PipelineConfig, member_id: str, output_format: str) -> None:
    """Mostra detalhes de um perfil específico."""
    profiles_dir = config.posts_dir / "profiles" / "json"
    profile_file = profiles_dir / f"{member_id}.json"

    if not profile_file.exists():
        console.print(f"❌ Perfil não encontrado: {member_id}")
        raise typer.Exit(1)

    try:
        with open(profile_file) as f:
            profile_data = json.load(f)

        if output_format == "json":
            console.print(json.dumps(profile_data, indent=2, ensure_ascii=False))
        else:
            console.print(
                Panel(
                    f"[bold]Nome:[/bold] {profile_data.get('name', 'Unknown')}\n"
                    f"[bold]ID do Membro:[/bold] {member_id}\n"
                    f"[bold]Mensagens:[/bold] {profile_data.get('message_count', 0)}\n"
                    f"[bold]Primeira Atividade:[/bold] {profile_data.get('first_seen', 'Unknown')}\n"
                    f"[bold]Última Atividade:[/bold] {profile_data.get('last_seen', 'Unknown')}\n"
                    f"[bold]Última Atualização:[/bold] {profile_data.get('last_updated', 'Unknown')}\n\n"
                    f"[bold]Descrição:[/bold]\n{profile_data.get('description', 'Nenhuma descrição disponível')}\n\n"
                    f"[bold]Tópicos Principais:[/bold] {', '.join(profile_data.get('main_topics', []))}\n"
                    f"[bold]Estilo de Comunicação:[/bold] {profile_data.get('communication_style', 'Unknown')}",
                    title=f"👤 Perfil: {profile_data.get('name', member_id)}",
                    border_style="blue",
                )
            )
    except Exception as e:
        console.print(f"❌ Erro ao ler perfil: {e}")
        raise typer.Exit(1)


def _generate_profiles(config: PipelineConfig, zip_path: Path) -> None:
    """Gera perfis a partir de um ZIP do WhatsApp."""
    if not zip_path.exists():
        console.print(f"❌ Arquivo ZIP não encontrado: {zip_path}")
        raise typer.Exit(1)

    console.print(f"👥 Gerando perfis a partir de: {zip_path}")

    try:
        # Create processor with the ZIP file
        temp_config = PipelineConfig(
            zip_files=[zip_path],
            posts_dir=config.posts_dir,
            llm=LLMConfig(),
            enrichment=EnrichmentConfig(),
            cache=CacheConfig(),
            profiles=ProfilesConfig(),
            anonymization=AnonymizationConfig(),
            rag=RAGConfig(),
        )
        processor = UnifiedProcessor(temp_config)

        # Generate profiles (this would need implementation in processor)
        console.print("🔄 Processando mensagens para geração de perfis...")

        # For now, show what would be done
        console.print("✅ Perfis seriam gerados (funcionalidade em desenvolvimento)")
        console.print("💡 Use 'egregora process' com dados reais para gerar perfis automaticamente")

    except Exception as e:
        console.print(f"❌ Erro durante geração de perfis: {e}")
        raise typer.Exit(1)


def _clean_profiles(config: PipelineConfig) -> None:
    """Remove perfis antigos ou inválidos."""
    profiles_dir = config.posts_dir / "profiles" / "json"

    if not profiles_dir.exists():
        console.print("📁 Nenhum diretório de perfis encontrado")
        return

    profile_files = list(profiles_dir.glob("*.json"))
    removed_count = 0

    for profile_file in profile_files:
        try:
            with open(profile_file) as f:
                json.load(f)  # Validate JSON
        except Exception:
            profile_file.unlink()
            removed_count += 1
            console.print(f"🗑️  Removido perfil corrompido: {profile_file.name}")

    if removed_count == 0:
        console.print("✅ Todos os perfis estão válidos")
    else:
        console.print(f"✅ Removidos {removed_count} perfis corrompidos")


# Original helper functions (preserved from the original main function)
def _list_groups_and_exit(processor: UnifiedProcessor) -> None:
    """Lista grupos descobertos e sai."""
    sources_to_process, real_groups, virtual_groups = processor._collect_sources()

    console.print(Panel("[bold green]📋 Grupos Descobertos[/bold green]"))

    if real_groups:
        console.print("\n[bold yellow]📱 Grupos Reais (do WhatsApp):[/bold yellow]")
        for slug, source in real_groups.items():
            date_range = f"{source.earliest_date} → {source.latest_date}"
            console.print(f"  • {source.name} ({slug}): {date_range}")

    if virtual_groups:
        console.print("\n[bold cyan]🔗 Grupos Virtuais (mesclados):[/bold cyan]")
        for slug, config in virtual_groups.items():
            console.print(f"  • {config.name} ({slug}): mescla {len(config.source_groups)} grupos")

    console.print(f"\n[dim]Total: {len(sources_to_process)} grupo(s) para processar[/dim]")
    raise typer.Exit()


def _dry_run_and_exit(
    processor: UnifiedProcessor,
    days: int | None,
    from_date: date | None,
    to_date: date | None,
) -> None:
    """Executa dry run e sai."""
    console.print(
        Panel(
            "[bold blue]🔍 Modo DRY RUN[/bold blue]\n"
            "Mostrando o que seria processado sem executar",
            border_style="blue",
        )
    )

    plans = processor.plan_runs(days=days, from_date=from_date, to_date=to_date)
    if not plans:
        console.print("[yellow]Nenhum grupo foi encontrado com os filtros atuais.[/yellow]")
        console.print("Ajuste EGREGORA__POSTS_DIR ou coloque exports em data/whatsapp_zips/.\n")
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
            if len(plan.target_dates) <= 10:
                formatted_dates = ", ".join(str(d) for d in plan.target_dates)
            else:
                first_5 = ", ".join(str(d) for d in plan.target_dates[:5])
                last_5 = ", ".join(str(d) for d in plan.target_dates[-5:])
                formatted_dates = f"{first_5}, ..., {last_5}"
            console.print(f"   Será gerado para {len(plan.target_dates)} dia(s): {formatted_dates}")
            total_posts += len(plan.target_dates)
        else:
            console.print("   Nenhuma post seria gerada (sem dados recentes)")

    console.print(f"\nResumo: {len(plans)} grupo(s) gerariam até {total_posts} post(s).")

    # Show quota estimation
    try:
        quota_info = processor.estimate_api_usage(days=days, from_date=from_date, to_date=to_date)
        console.print("\n📊 Estimativa de Uso da API:")
        console.print(f"   Chamadas para posts: {quota_info['post_calls']}")
        console.print(f"   Chamadas para enriquecimento: {quota_info['enrichment_calls']}")
        console.print(f"   Total de chamadas: {quota_info['total_api_calls']}")
        console.print(
            f"   Tempo estimado (tier gratuito): {quota_info['estimated_time_minutes']:.1f} minutos"
        )

        if quota_info["total_api_calls"] > 200:
            console.print(
                "\n[yellow]⚠️ Esta operação pode exceder a quota gratuita do Gemini[/yellow]"
            )
            console.print(
                "[dim]Tier gratuito: 15 chamadas/minuto. Considere processar em lotes menores.[/dim]"
            )

    except Exception as exc:
        console.print(f"\n[yellow]Não foi possível estimar uso da API: {exc}[/yellow]")

    console.print()
    raise typer.Exit()


def _process_and_display(
    processor: UnifiedProcessor,
    *,
    days: int | None,
    from_date: date | None,
    to_date: date | None,
) -> None:
    """Processa grupos e mostra resultado formatado."""

    # Show quota estimation before processing
    try:
        quota_info = processor.estimate_api_usage(days=days, from_date=from_date, to_date=to_date)
        if quota_info["total_api_calls"] > 15:
            console.print(
                Panel(
                    f"[yellow]⚠️ Esta operação fará {quota_info['total_api_calls']} chamadas à API[/yellow]\n"
                    f"Tempo estimado (tier gratuito): {quota_info['estimated_time_minutes']:.1f} minutos\n"
                    f"[dim]O processamento pode ser interrompido por limites de quota.[/dim]",
                    border_style="yellow",
                    title="Estimativa de Quota",
                )
            )

    except Exception as exc:
        console.print(f"\n[yellow]Não foi possível estimar uso da API: {exc}[/yellow]")

    console.print()

    console.print(Panel("[bold green]🚀 Processando Grupos[/bold green]"))

    results = processor.process_all(days=days, from_date=from_date, to_date=to_date)

    total = sum(len(v) for v in results.values())
    table = Table(
        title=f"📊 Resultado do Processamento ({total} posts geradas)",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Grupo", style="cyan", no_wrap=True)
    table.add_column("Posts Geradas", justify="center", style="green")
    table.add_column("Arquivos", style="dim")

    for group_slug, post_paths in results.items():
        files = ", ".join(p.name for p in post_paths[:3])
        if len(post_paths) > 3:
            files += f", +{len(post_paths) - 3} mais"
        table.add_row(group_slug, str(len(post_paths)), files)

    console.print(table)


def run() -> None:
    """Entry point used by the console script."""
    app()


# Maintain backward compatibility - if called without subcommand, default to process
def main(*args, **kwargs):
    """Backward compatibility wrapper."""
    return process_command(*args, **kwargs)


if __name__ == "__main__":
    run()
