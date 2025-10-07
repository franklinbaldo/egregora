"""Utilities to download WhatsApp exports from a shared Google Drive folder."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import gdown


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download all WhatsApp .zip exports from a public Google Drive folder "
            "into a target directory."
        )
    )
    parser.add_argument(
        "drive_url",
        help="Shareable URL for the Google Drive folder containing WhatsApp exports.",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="data/whatsapp_zips",
        help=(
            "Directory where the downloaded .zip files will be stored. Defaults to "
            "'data/whatsapp_zips'."
        ),
    )
    return parser.parse_args(argv)


def download_drive_folder(drive_url: str, destination: Path) -> list[Path]:
    """Download ``*.zip`` files from *drive_url* into *destination*.

    The folder is first downloaded into a temporary directory to avoid mixing
    unexpected files with the workspace. Only files with a ``.zip`` extension
    are moved into *destination*.
    """

    destination.mkdir(parents=True, exist_ok=True)

    downloaded_files: list[Path] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        gdown.download_folder(  # type: ignore[call-arg]
            url=drive_url,
            output=tmp_dir,
            quiet=False,
            use_cookies=False,
        )
        for zip_path in Path(tmp_dir).rglob("*.zip"):
            target_path = destination / zip_path.name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(zip_path), target_path)
            downloaded_files.append(target_path)
    return downloaded_files


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    destination = Path(args.output_dir)

    try:
        downloaded_files = download_drive_folder(args.drive_url, destination)
    except Exception as exc:  # pragma: no cover - defensive logging for CI
        print(f"[download_drive_zips] Failed to download folder: {exc}", file=sys.stderr)
        return 1

    if not downloaded_files:
        print(
            "[download_drive_zips] No .zip files were found in the shared folder.",
            file=sys.stderr,
        )
        return 1

    print(
        f"[download_drive_zips] Downloaded {len(downloaded_files)} ZIP files to {destination}"
    )
    for file_path in downloaded_files:
        print(f" - {file_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
