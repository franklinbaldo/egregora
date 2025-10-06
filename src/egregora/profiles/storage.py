"""Persistence helpers for participant profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Tuple

from .profile import ParticipantProfile


@dataclass(slots=True)
class ProfileRepository:
    """Manage profile persistence on disk and build a documentation index."""

    data_dir: Path
    docs_dir: Path

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.docs_dir = Path(self.docs_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def load(self, identifier: str) -> ParticipantProfile | None:
        """Return the profile for *identifier* or ``None`` when missing."""

        path = self._json_path(identifier)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return ParticipantProfile.from_dict(payload)

    def save(self, identifier: str, profile: ParticipantProfile) -> None:
        """Persist *profile* to JSON outputs."""

        json_path = self._json_path(identifier)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def iter_profiles(self) -> Iterator[Tuple[str, ParticipantProfile]]:
        """Yield ``(identifier, profile)`` pairs for stored profiles."""

        for path in sorted(self.data_dir.glob("*.json")):
            identifier = path.stem
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            try:
                profile = ParticipantProfile.from_dict(payload)
            except Exception:
                continue
            yield identifier, profile

    def write_index(self) -> None:
        """Regenerate the Markdown index listing all profiles."""

        entries = []
        for identifier, profile in self.iter_profiles():
            entries.append(
                (
                    profile.last_updated,
                    identifier,
                    profile.member_id,
                    profile.analysis_version,
                )
            )

        index_path = self.docs_dir / "index.md"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = ["# Perfis dos Participantes", ""]
        lines.append(
            "Perfis analíticos atualizados automaticamente conforme a participação nos grupos."
        )
        lines.append("")

        if not entries:
            lines.append("_Nenhum perfil disponível no momento._")
        else:
            lines.append("| Membro | Arquivo JSON | Última atualização | Versão |")
            lines.append("| --- | --- | --- | --- |")
            for last_updated, identifier, member_id, version in sorted(
                entries, key=lambda item: item[0], reverse=True
            ):
                date_text = _format_datetime(last_updated)
                json_link = f"../../data/profiles/{identifier}.json"
                lines.append(
                    f"| {member_id} | [ver dados]({json_link}) | {date_text} | {version} |"
                )

        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _json_path(self, identifier: str) -> Path:
        return self.data_dir / f"{identifier}.json"


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    try:
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value.isoformat()


__all__ = ["ProfileRepository"]
