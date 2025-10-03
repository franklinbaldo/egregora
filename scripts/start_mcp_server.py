"""Entry point for launching the MCP RAG server from the command line."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from egregora.mcp_server.server import main as run_server


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
    asyncio.run(run_server(config_path=args.config))


if __name__ == "__main__":  # pragma: no cover
    cli()
