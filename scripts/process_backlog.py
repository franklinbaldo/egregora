"""Command line entry point for WhatsApp backlog processing."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
from typing import List

from egregora.backlog import BacklogProcessor, PendingDay
from egregora.config import PipelineConfig

DEFAULT_ZIP_DIR = Path("data/zips/")
DEFAULT_OUTPUT_DIR = Path("docs/reports/daily/")


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _filter_days(days: Iterable[PendingDay], start: date | None, end: date | None) -> List[PendingDay]:
    filtered: List[PendingDay] = []
    for day in days:
        if start and day.date < start:
            continue
        if end and day.date > end:
            continue
        filtered.append(day)
    return filtered


def _describe_scan(days: List[PendingDay]) -> str:
    total = len(days)
    processed = sum(1 for day in days if day.already_processed)
    pending = total - processed
    if not days:
        return "Nenhum arquivo .zip encontrado."

    first = days[0].date.isoformat()
    last = days[-1].date.isoformat()
    return (
        "📊 Análise de Backlog\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Total de zips encontrados: {total}\n"
        f"Newsletters já existentes: {processed}\n"
        f"Dias pendentes: {pending}\n\n"
        f"Período: {first} até {last}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Processa backlog de newsletters.")
    parser.add_argument("--scan", action="store_true", help="Apenas analisa e mostra pendências")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem processar")
    parser.add_argument("--start-date", dest="start_date", help="Data inicial (YYYY-MM-DD)")
    parser.add_argument(
        "--end-date",
        dest="end_date",
        help="Data final (YYYY-MM-DD). Padrão: hoje",
    )
    parser.add_argument("--max-per-run", type=int, help="Processar no máximo N dias")
    parser.add_argument("--resume", action="store_true", help="Continuar do último checkpoint")
    parser.add_argument("--force-rebuild", action="store_true", help="Reprocessar mesmo se já existe")
    parser.add_argument("--skip-enrichment", action="store_true", help="Pular enriquecimento de URLs")
    parser.add_argument(
        "--zip-dir",
        default=str(DEFAULT_ZIP_DIR),
        help=f"Diretório com zips (padrão: {DEFAULT_ZIP_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Diretório de saída (padrão: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--checkpoint-file",
        default=None,
        help="Arquivo de checkpoint (padrão: ./cache/backlog_checkpoint.json)",
    )
    parser.add_argument(
        "--config",
        dest="config",
        default=None,
        help="Arquivo YAML com configurações específicas do backlog",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    zip_dir = Path(args.zip_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline_config = PipelineConfig.with_defaults(
        zips_dir=zip_dir,
        newsletters_dir=output_dir,
        media_dir=output_dir / "media",
    )

    processor = BacklogProcessor(
        config_path=args.config,
        checkpoint_file=args.checkpoint_file,
        pipeline_config=pipeline_config,
    )

    pending_days = processor.scan_pending_days(zip_dir, output_dir)
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date) if args.end_date else None
    if args.end_date is None:
        end_date = date.today()

    filtered = _filter_days(pending_days, start_date, end_date)

    if args.scan:
        print(_describe_scan(filtered))
        estimate = processor.estimate_costs([day for day in filtered if not day.already_processed])
        if estimate.total_days:
            print(
                "\nEstatísticas estimadas:\n"
                f"- Total de mensagens: ~{estimate.total_messages}\n"
                f"- Total de URLs: ~{estimate.total_urls}\n"
                f"- Tempo estimado: ~{estimate.estimated_time_seconds/60:.1f} min\n"
                f"- Custo estimado: ${estimate.estimated_cost_usd:.2f} USD"
            )
        return

    max_per_run = args.max_per_run
    skip_enrichment = args.skip_enrichment or not processor.backlog_config.enrichment.enabled
    force_rebuild = args.force_rebuild

    items_to_process = filtered
    if not force_rebuild:
        items_to_process = [day for day in filtered if not day.already_processed]

    if args.dry_run:
        results = processor.process_batch(
            items_to_process,
            max_per_run=max_per_run,
            skip_enrichment=skip_enrichment,
            force_rebuild=force_rebuild,
            dry_run=True,
        )
    elif args.resume:
        results = processor.resume_processing(
            items_to_process,
            skip_enrichment=skip_enrichment,
            force_rebuild=force_rebuild,
        )
    else:
        results = processor.process_batch(
            items_to_process,
            max_per_run=max_per_run,
            skip_enrichment=skip_enrichment,
            force_rebuild=force_rebuild,
        )

    for result in results:
        status = result.status.upper()
        base = f"{result.date.isoformat()} - {status}"
        if result.status == "success" and result.output_path:
            print(f"{base} -> {result.output_path}")
        elif result.status == "failed":
            print(f"{base} ({result.error})")
        else:
            print(base)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
