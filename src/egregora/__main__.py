"""Command-line entry point for the Egregora newsletter pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

from .config import PipelineConfig
from .pipeline import generate_newsletter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera newsletters diárias a partir dos exports do WhatsApp."
    )
    parser.add_argument(
        "--zips-dir",
        type=Path,
        default=None,
        help="Pasta onde os arquivos .zip diários estão armazenados.",
    )
    parser.add_argument(
        "--newsletters-dir",
        type=Path,
        default=None,
        help="Pasta onde as newsletters serão escritas.",
    )
    parser.add_argument(
        "--group-name",
        type=str,
        default=None,
        help="Nome do grupo a ser usado no cabeçalho da newsletter.",
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    timezone = ZoneInfo(args.timezone) if args.timezone else None
    config = PipelineConfig.with_defaults(
        zips_dir=args.zips_dir,
        newsletters_dir=args.newsletters_dir,
        group_name=args.group_name,
        model=args.model,
        timezone=timezone,
    )

    result = generate_newsletter(config, days=args.days)

    if not result.previous_newsletter_found:
        print(
            f"[Aviso] Newsletter de ontem ({result.previous_newsletter_path.name}) não encontrada; prossegui sem esse contexto."
        )

    processed = ", ".join(day.isoformat() for day in result.processed_dates)
    print(f"[OK] Newsletter criada em {result.output_path} usando dias {processed}.")
    return 0


def run() -> None:
    """Entry point used by the console script."""

    raise SystemExit(main())


if __name__ == "__main__":
    run()
