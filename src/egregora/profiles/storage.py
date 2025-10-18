"""Persistence helpers for participant profiles."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from ..markdown_utils import format_markdown
from .profile import ParticipantProfile


def _render_profile_markdown(profile: ParticipantProfile) -> str:
    markdown = profile.to_markdown().strip()
    markdown = format_markdown(markdown)
    if not markdown:
        markdown = f"# Perfil Analítico: {profile.member_id}\n\n(Conteúdo indisponível no momento.)"
    disclaimer = (
        "> [!NOTE]\n"
        "> Perfil gerado automaticamente pelo pipeline Egregora.\n"
        "> Revise antes de publicar externamente."
    )
    if not markdown.endswith("\n"):
        markdown += "\n"
    markdown_content = f"{disclaimer}\n\n{markdown}"
    return format_markdown(markdown_content)


def _render_index_markdown(entries: Iterable[tuple[datetime | None, str, str, int]]) -> str:
    entries = list(entries)
    total_profiles = len(entries)
    latest_update = max((entry[0] for entry in entries), default=None)
    highest_version = max((entry[3] for entry in entries), default=0)

    lines: list[str] = ["# Perfis dos Participantes", ""]
    lines.append(
        "Resumo automatizado para acompanhar o módulo de perfis sem expor dados específicos."
    )
    lines.append("")
    lines.append(f"- Perfis monitorados: {total_profiles}")
    lines.append(f"- Última atualização registrada: {_format_datetime(latest_update)}")
    lines.append(f"- Maior versão gerada: {highest_version}")
    lines.append("")
    lines.append("## Onde encontrar os dados")
    lines.append("- JSON anonimizado: `data/profiles/` (uso interno e integrações).")
    lines.append("- Relatórios em Markdown: `docs/profiles/` para revisão antes da publicação.")
    lines.append(
        "- Esta página permanece genérica por padrão; edite-a manualmente caso queira destacar perfis específicos."
    )
    lines.append("")
    lines.append("## Fluxo sugerido para publicar no site")
    lines.append("1. Revise os arquivos em `docs/profiles/`.")
    lines.append("2. Copie os perfis aprovados para uma seção pública da documentação.")
    lines.append("3. Atualize este índice com links curados, se necessário.")
    lines.append(
        "4. Remova arquivos antigos de `data/profiles/` quando quiser reiniciar as análises."
    )
    lines.append("")
    lines.append(
        "> Dica: utilize `uv run egregora --config egregora.toml --dry-run` para validar quais perfis seriam afetados antes de consumir cota do modelo."
    )
    lines.append("")
    lines.append("## Perfis monitorados")

    for _, identifier, member_id, version in sorted(entries):
        lines.append(f"- `{identifier}` — {member_id} (versão {version})")

    return "\n".join(lines) + "\n"


@dataclass(slots=True)
class ProfileStorage:
    """Handle serialization/deserialization of profile data."""

    data_dir: Path
    docs_dir: Path

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.docs_dir = Path(self.docs_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def load(self, identifier: str) -> ParticipantProfile | None:
        path = self._json_path(identifier)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        try:
            return ParticipantProfile.from_dict(payload)
        except (ValueError, TypeError, ValidationError):
            return None

    def save(self, identifier: str, profile: ParticipantProfile) -> None:
        json_path = self._json_path(identifier)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        markdown_path = self.docs_dir / f"{identifier}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(_render_profile_markdown(profile), encoding="utf-8")

    def iter_profiles(self) -> Iterator[tuple[str, ParticipantProfile]]:
        for path in sorted(self.data_dir.glob("*.json")):
            identifier = path.stem
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            try:
                profile = ParticipantProfile.from_dict(payload)
            except (ValueError, TypeError, ValidationError):
                continue
            yield identifier, profile

    def _json_path(self, identifier: str) -> Path:
        return self.data_dir / f"{identifier}.json"


@dataclass(slots=True)
class ProfileIndexWriter:
    """Render and persist the Markdown index summarising stored profiles."""

    docs_dir: Path

    def write(self, entries: Iterable[tuple[str, ParticipantProfile]]) -> None:
        rendered_entries = [
            (profile.last_updated, identifier, profile.member_id, profile.analysis_version)
            for identifier, profile in entries
        ]
        markdown = _render_index_markdown(rendered_entries)
        index_path = Path(self.docs_dir) / "index.md"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(markdown, encoding="utf-8")


@dataclass(slots=True)
class ProfileRepository:
    """Manage profile persistence on disk and build a documentation index."""

    data_dir: Path
    docs_dir: Path

    def __post_init__(self) -> None:
        self._storage = ProfileStorage(self.data_dir, self.docs_dir)
        self._index_writer = ProfileIndexWriter(self.docs_dir)

    def load(self, identifier: str) -> ParticipantProfile | None:
        """Return the profile for *identifier* or ``None`` when missing."""

        return self._storage.load(identifier)

    def save(self, identifier: str, profile: ParticipantProfile) -> None:
        """Persist *profile* to JSON outputs and generated Markdown."""

        self._storage.save(identifier, profile)

    def iter_profiles(self) -> Iterator[tuple[str, ParticipantProfile]]:
        """Yield ``(identifier, profile)`` pairs for stored profiles."""

        yield from self._storage.iter_profiles()

    def write_index(self) -> None:
        """Regenerate the Markdown index listing all profiles."""

        self._index_writer.write(self.iter_profiles())


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    try:
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value.isoformat()


__all__ = ["ProfileRepository"]
