"""Command-line entry point for the Egregora newsletter pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

from .config import PipelineConfig
from .discover import discover_identifier, format_cli_message
from .processor import UnifiedProcessor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera newsletters diárias a partir dos exports do WhatsApp."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Arquivo TOML de configuração (recomendado).",
    )
    parser.add_argument(
        "--zips-dir",
        type=Path,
        default=None,
        help="Diretório onde os arquivos .zip diários estão armazenados.",
    )
    parser.add_argument(
        "--newsletters-dir",
        type=Path,
        default=None,
        help="Diretório onde as newsletters serão escritas.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Nome do modelo Gemini a ser usado.",
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default=None,
        help="Timezone IANA (ex.: America/Porto_Velho) usado para marcar a data de hoje.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=2,
        help="Quantidade de dias mais recentes a incluir no prompt (padrão: 2).",
    )
    parser.add_argument(
        "--disable-enrichment",
        action="store_true",
        help="Desativa o enriquecimento de conteúdos compartilhados.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista grupos descobertos e sai.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a execução e mostra quais newsletters seriam geradas.",
    )

    subparsers = parser.add_subparsers(dest="command")
    discover_parser = subparsers.add_parser(
        "discover",
        help="Calcula o identificador anônimo para um telefone ou apelido.",
    )
    discover_parser.add_argument(
        "value",
        help="Telefone ou apelido a ser anonimizado.",
    )
    discover_parser.add_argument(
        "--format",
        choices=["human", "short", "full"],
        default="human",
        help="Formato preferido ao exibir o resultado.",
    )
    discover_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Imprime apenas o identificador no formato escolhido.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.days <= 0:
        parser.error("--days deve ser maior que zero")

    timezone_override = None
    if args.timezone:
        try:
            timezone_override = ZoneInfo(args.timezone)
        except Exception as exc:  # pragma: no cover - defensive
            parser.error(f"Timezone '{args.timezone}' não é válido: {exc}")

    if args.command == "discover":
        value = args.value.strip()
        if not value:
            print("Erro: informe um telefone ou apelido válido.", file=sys.stderr)
            return 1

        try:
            result = discover_identifier(value)
        except ValueError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1

        if args.quiet:
            print(result.get(args.format))
        else:
            print(format_cli_message(result, preferred_format=args.format))
        return 0

    # Load config (with TOML support)
    if args.config:
        if not args.config.exists():
            parser.error(f"Arquivo de configuração '{args.config}' não encontrado")
        config = PipelineConfig.from_toml(args.config)
    else:
        config = PipelineConfig.with_defaults(
            zips_dir=args.zips_dir,
            newsletters_dir=args.newsletters_dir,
            model=args.model,
            timezone=timezone_override,
        )

    # Essential CLI overrides still têm precedência sobre o TOML
    if args.zips_dir:
        config.zips_dir = args.zips_dir
    if args.newsletters_dir:
        config.newsletters_dir = args.newsletters_dir
    if args.model:
        config.model = args.model
    if timezone_override:
        config.timezone = timezone_override
    if args.disable_enrichment:
        config.enrichment.enabled = False

    processor = UnifiedProcessor(config)

    # List mode
    if args.list:
        groups = processor.list_groups()

        print("\n" + "=" * 60)
        print("📁 DISCOVERED GROUPS")
        print("=" * 60 + "\n")

        for slug, info in sorted(groups.items()):
            icon = "📺" if info["type"] == "virtual" else "📝"
            print(f"{icon} {info['name']}")
            print(f"   Slug: {slug}")
            print(f"   Exports: {info['export_count']}")
            print(f"   Dates: {info['date_range'][0]} to {info['date_range'][1]}")

            if info["type"] == "real" and info["in_virtual"]:
                print(f"   Part of: {', '.join(info['in_virtual'])}")
            elif info["type"] == "virtual":
                print(f"   Merges: {', '.join(info['merges'])}")

            print()

        print("=" * 60 + "\n")
        return 0

    if args.dry_run:
        plans = processor.plan_runs(days=args.days)

        print("\n" + "=" * 60)
        print("🧪 DRY RUN — NENHUM MODELO SERÁ CHAMADO")
        print("=" * 60 + "\n")

        if not plans:
            print("Nenhum grupo foi encontrado com os filtros atuais.")
            print("Use --zips-dir ou ajuste seu arquivo TOML para apontar para os exports corretos.\n")
            return 0

        total_newsletters = 0
        for plan in plans:
            icon = "📺" if plan.is_virtual else "📝"
            print(f"{icon} {plan.name} ({plan.slug})")
            print(f"   Exports disponíveis: {plan.export_count}")
            if plan.is_virtual and plan.merges:
                print(f"   Grupos combinados: {', '.join(plan.merges)}")

            if plan.available_dates:
                print(
                    f"   Intervalo disponível: {plan.available_dates[0]} → {plan.available_dates[-1]}"
                )
            else:
                print("   Nenhuma data disponível nos exports")

            if plan.target_dates:
                formatted_dates = ", ".join(str(d) for d in plan.target_dates)
                print(f"   Será gerado para {len(plan.target_dates)} dia(s): {formatted_dates}")
                total_newsletters += len(plan.target_dates)
            else:
                print("   Nenhuma newsletter seria gerada (sem dados recentes)")

            print()

        print("=" * 60)
        print(
            f"Resumo: {len(plans)} grupo(s) seriam processados gerando até {total_newsletters} newsletter(s)."
        )
        print("Use --config para ajustes avançados.\n")
        return 0

    # Process mode
    print("\n" + "=" * 60)
    print("🚀 PROCESSING WITH AUTO-DISCOVERY")
    print("=" * 60)

    results = processor.process_all(days=args.days)

    # Summary
    print("\n" + "=" * 60)
    print("✅ COMPLETE")
    print("=" * 60 + "\n")

    total = sum(len(v) for v in results.values())
    print(f"Groups processed: {len(results)}")
    print(f"Newsletters generated: {total}\n")

    for slug, newsletters in sorted(results.items()):
        print(f"  {slug}: {len(newsletters)} newsletters")

    print("\n" + "=" * 60 + "\n")
    return 0


def run() -> None:
    """Entry point used by the console script."""

    raise SystemExit(main())


if __name__ == "__main__":
    run()
