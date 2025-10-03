"""Command-line entry point for the Egregora newsletter pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

from .config import PipelineConfig
from .discover import discover_identifier, format_cli_message
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
    parser.add_argument(
        "--enable-enrichment",
        action="store_true",
        help="Ativa explicitamente o enriquecimento de conteúdos compartilhados.",
    )
    parser.add_argument(
        "--disable-enrichment",
        action="store_true",
        help="Desativa o enriquecimento de conteúdos compartilhados.",
    )
    parser.add_argument(
        "--relevance-threshold",
        type=int,
        default=None,
        help="Relevância mínima (1-5) para incluir itens enriquecidos no prompt.",
    )
    parser.add_argument(
        "--max-enrichment-items",
        type=int,
        default=None,
        help="Número máximo de links analisados por execução (padrão: 50).",
    )
    parser.add_argument(
        "--max-enrichment-time",
        type=float,
        default=None,
        help="Tempo máximo (segundos) destinado ao enriquecimento (padrão: 120).",
    )
    parser.add_argument(
        "--enrichment-model",
        type=str,
        default=None,
        help="Modelo Gemini utilizado nas análises de links (padrão: gemini-2.0-flash-exp).",
    )
    parser.add_argument(
        "--enrichment-context-window",
        type=int,
        default=None,
        help="Quantidade de mensagens antes/depois usadas como contexto (padrão: 3).",
    )
    parser.add_argument(
        "--analysis-concurrency",
        type=int,
        default=None,
        help="Quantidade máxima de análises LLM simultâneas (padrão: 5).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Diretório para armazenar o cache de análises.",
    )
    parser.add_argument(
        "--disable-cache",
        action="store_true",
        help="Desativa completamente o cache persistente.",
    )
    parser.add_argument(
        "--cache-cleanup-days",
        type=int,
        default=None,
        help="Remove análises cujo último uso é mais antigo que N dias.",
    )
    parser.add_argument(
        "--cache-max-disk-mb",
        type=int,
        default=None,
        help="Define um limite (em MB) para o uso de disco do cache.",
    )

    parser.add_argument(
        "--disable-anonymization",
        action="store_true",
        help="Desativa a anonimização de autores antes do processamento.",
    )
    parser.add_argument(
        "--anonymization-format",
        choices=["human", "short", "full"],
        default=None,
        help="Formato dos identificadores anônimos (padrão: human).",
    )
    parser.add_argument(
        "--double-check-newsletter",
        action="store_true",
        help="Executa uma segunda chamada ao LLM para revisar a newsletter em busca de PII.",
    )
    parser.add_argument(
        "--review-model",
        type=str,
        default=None,
        help="Modelo opcional utilizado na revisão de privacidade (padrão: mesmo da geração).",
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

    timezone = ZoneInfo(args.timezone) if args.timezone else None
    config = PipelineConfig.with_defaults(
        zips_dir=args.zips_dir,
        newsletters_dir=args.newsletters_dir,
        group_name=args.group_name,
        model=args.model,
        timezone=timezone,
    )

    if args.disable_anonymization:
        config.anonymization.enabled = False
    if args.anonymization_format:
        config.anonymization.output_format = args.anonymization_format
    if args.double_check_newsletter:
        config.privacy.double_check_newsletter = True
    if args.review_model:
        config.privacy.review_model = args.review_model

    enrichment = config.enrichment
    if args.enable_enrichment:
        enrichment.enabled = True
    if args.disable_enrichment:
        enrichment.enabled = False
    if args.relevance_threshold is not None:
        enrichment.relevance_threshold = max(1, min(5, args.relevance_threshold))
    if args.max_enrichment_items is not None and args.max_enrichment_items > 0:
        enrichment.max_links = args.max_enrichment_items
    if args.max_enrichment_time is not None and args.max_enrichment_time > 0:
        enrichment.max_total_enrichment_time = args.max_enrichment_time
    if args.enrichment_model:
        enrichment.enrichment_model = args.enrichment_model
    if args.enrichment_context_window is not None and args.enrichment_context_window >= 0:
        enrichment.context_window = args.enrichment_context_window
    if args.analysis_concurrency is not None and args.analysis_concurrency > 0:
        enrichment.max_concurrent_analyses = args.analysis_concurrency

    cache_config = config.cache
    if args.cache_dir:
        cache_config.cache_dir = args.cache_dir
    if args.disable_cache:
        cache_config.enabled = False
    if args.cache_cleanup_days is not None and args.cache_cleanup_days >= 0:
        cache_config.auto_cleanup_days = args.cache_cleanup_days
    if args.cache_max_disk_mb is not None and args.cache_max_disk_mb > 0:
        cache_config.max_disk_mb = args.cache_max_disk_mb

    result = generate_newsletter(config, days=args.days)

    if not result.previous_newsletter_found:
        print(
            f"[Aviso] Newsletter de ontem ({result.previous_newsletter_path.name}) não encontrada; prossegui sem esse contexto."
        )

    if result.enrichment is None:
        if enrichment.enabled:
            print("[Aviso] Enriquecimento de conteúdos não retornou resultados.")
    else:
        relevant = len(
            result.enrichment.relevant_items(enrichment.relevance_threshold)
        )
        print(
            f"[Resumo] Enriquecimento considerou {len(result.enrichment.items)} itens; "
            f"{relevant} atenderam à relevância mínima de {enrichment.relevance_threshold}."
        )

    processed = ", ".join(day.isoformat() for day in result.processed_dates)
    print(f"[OK] Newsletter criada em {result.output_path} usando dias {processed}.")
    return 0


def run() -> None:
    """Entry point used by the console script."""

    raise SystemExit(main())


if __name__ == "__main__":
    run()
