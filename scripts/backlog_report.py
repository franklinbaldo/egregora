"""Generate backlog progress reports."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

from egregora.backlog import BacklogProcessor, PendingDay
from egregora.config import PipelineConfig

DEFAULT_ZIP_DIR = Path("data/zips/")
DEFAULT_OUTPUT_DIR = Path("docs/reports/daily/")


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera relatório do backlog.")
    parser.add_argument("--detailed", action="store_true", help="Mostra detalhes por dia")
    parser.add_argument("--output", help="Exporta relatório para JSON")
    parser.add_argument("--start-date", dest="start_date", help="Filtra datas a partir de")
    parser.add_argument("--end-date", dest="end_date", help="Filtra datas até")
    parser.add_argument(
        "--zip-dir",
        default=str(DEFAULT_ZIP_DIR),
        help=f"Diretório com zips (padrão: {DEFAULT_ZIP_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Diretório de newsletters (padrão: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument("--config", help="Arquivo de configuração do backlog")
    parser.add_argument("--checkpoint-file", help="Arquivo de checkpoint")
    return parser


def _filter_days(days: List[PendingDay], start: date | None, end: date | None):
    filtered: List[PendingDay] = []
    for day in days:
        if start and day.date < start:
            continue
        if end and day.date > end:
            continue
        filtered.append(day)
    return filtered


def _build_report(processor: BacklogProcessor, days: List[PendingDay]) -> Dict[str, Any]:
    pending_days = [day for day in days if not day.already_processed]
    estimate = processor.estimate_costs(pending_days)
    checkpoint = asdict(processor.checkpoint_state)
    return {
        "total_days": len(days),
        "pending_days": len(pending_days),
        "processed_days": len(days) - len(pending_days),
        "date_range": [days[0].date.isoformat(), days[-1].date.isoformat()] if days else None,
        "estimate": {
            "total_messages": estimate.total_messages,
            "total_urls": estimate.total_urls,
            "estimated_cost_usd": estimate.estimated_cost_usd,
            "estimated_time_minutes": round(estimate.estimated_time_seconds / 60, 2),
        },
        "checkpoint": checkpoint,
    }


def _print_report(report: Dict[str, Any], *, detailed: bool, days: List[PendingDay]) -> None:
    print("📈 Relatório de Progresso")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Total de dias: {report['total_days']}")
    print(f"Dias pendentes: {report['pending_days']}")
    print(f"Dias processados: {report['processed_days']}")

    if report["date_range"]:
        print(f"Período: {report['date_range'][0]} → {report['date_range'][1]}")

    estimate = report["estimate"]
    print("\nEstimativas:")
    print(f"- Mensagens: ~{estimate['total_messages']}")
    print(f"- URLs: ~{estimate['total_urls']}")
    print(f"- Custo: ${estimate['estimated_cost_usd']:.2f} USD")
    print(f"- Tempo: ~{estimate['estimated_time_minutes']:.1f} min")

    checkpoint = report["checkpoint"]
    last_processed = checkpoint.get("last_processed_date")
    if last_processed:
        print(f"\nÚltimo checkpoint: {last_processed}")
    if checkpoint.get("failed_dates"):
        print("Falhas registradas:")
        for failure in checkpoint["failed_dates"]:
            print(f"  - {failure}")

    if detailed and days:
        print("\nPendências detalhadas:")
        for day in days:
            status = "OK" if day.already_processed else "pendente"
            print(
                f"- {day.date.isoformat()} ({status}) — mensagens: {day.message_count}, URLs: {day.url_count}, participantes: {day.participant_count}"
            )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    zip_dir = Path(args.zip_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()

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

    days = processor.scan_pending_days(zip_dir, output_dir)
    start = _parse_date(args.start_date)
    end = _parse_date(args.end_date)
    if start or end:
        days = _filter_days(days, start, end)

    report = _build_report(processor, days)

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    _print_report(report, detailed=args.detailed, days=days)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
