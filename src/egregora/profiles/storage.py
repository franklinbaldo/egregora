"""Persistence helpers for participant profiles."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..markdown_utils import format_markdown
from .profile import ParticipantProfile


@dataclass(slots=True)
#TODO: This class has a lot of logic for loading, saving, and indexing profiles. It could be split into smaller classes.
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

    #TODO: The markdown generation is a bit complex.
    def save(self, identifier: str, profile: ParticipantProfile) -> None:
        """Persist *profile* to JSON outputs and generated Markdown."""

        json_path = self._json_path(identifier)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        markdown = profile.to_markdown().strip()
        markdown = format_markdown(markdown)
        if not markdown:
            markdown = (
                f"# Perfil Analítico: {profile.member_id}\n\n(Conteúdo indisponível no momento.)"
            )
        disclaimer = (
            "> [!NOTE]\n"
            "> Perfil gerado automaticamente pelo pipeline Egregora.\n"
            "> Revise antes de publicar externamente."
        )
        if not markdown.endswith("\n"):
            markdown += "\n"
        markdown_content = f"{disclaimer}\n\n{markdown}"
        markdown_content = format_markdown(markdown_content)

        markdown_path = self.docs_dir / f"{identifier}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown_content, encoding="utf-8")

    def iter_profiles(self) -> Iterator[tuple[str, ParticipantProfile]]:
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

    #TODO: The content of the index file is hardcoded. It would be better to use a template engine for this.
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