"""Entry point for launching the MCP RAG server from the command line."""

from __future__ import annotations

import argparse
from pathlib import Path

from egregora.__main__ import launch_mcp_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inicia o servidor MCP do RAG da Egregora")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Caminho opcional para o arquivo de configuração TOML",
    )
    return parser.parse_args()


def cli() -> None:
    args = parse_args()
    launch_mcp_server(config_file=args.config)


if __name__ == "__main__":  # pragma: no cover
    cli()
