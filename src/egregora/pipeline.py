"""Core newsletter generation pipeline."""

from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import List, Sequence

try:  # pragma: no cover - executed only when dependency is missing
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows importing without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from .config import PipelineConfig

DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _require_google_dependency() -> None:
    """Ensure the optional google-genai dependency is available."""

    if genai is None or types is None:
        raise RuntimeError(
            "A dependência opcional 'google-genai' não está instalada. "
            "Instale-a para gerar newsletters (ex.: `pip install google-genai`)."
        )


@dataclass(slots=True)
class PipelineResult:
    """Information about an executed pipeline run."""

    output_path: Path
    processed_dates: List[date]
    previous_newsletter_path: Path
    previous_newsletter_found: bool


def find_date_in_name(path: Path) -> date | None:
    """Return the first YYYY-MM-DD date embedded in a filename."""

    match = DATE_IN_NAME_RE.search(path.name)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def list_zip_days(zips_dir: Path) -> list[tuple[date, Path]]:
    """Return available zip archives sorted by date."""

    zips: list[tuple[date, Path]] = []
    for path in zips_dir.glob("*.zip"):
        found_date = find_date_in_name(path)
        if found_date is not None:
            zips.append((found_date, path))
    zips.sort(key=lambda item: item[0])
    return zips


def read_zip_texts(zippath: Path) -> str:
    """Read all text files stored inside *zippath* in alphabetical order."""

    chunks: list[str] = []
    with zipfile.ZipFile(zippath, "r") as zipped:
        txt_names = sorted(name for name in zipped.namelist() if name.lower().endswith(".txt"))
        for name in txt_names:
            with zipped.open(name, "r") as file_handle:
                raw = file_handle.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            text = text.replace("\r\n", "\n")
            chunks.append(f"\n# Arquivo: {name}\n{text.strip()}\n")
    return "\n".join(chunks).strip()


def load_previous_newsletter(news_dir: Path, reference_date: date) -> tuple[Path, str | None]:
    """Load yesterday's newsletter if it exists."""

    yesterday = reference_date - timedelta(days=1)
    path = news_dir / f"{yesterday.isoformat()}.md"
    if path.exists():
        return path, path.read_text(encoding="utf-8")
    return path, None


def _format_transcript_section_header(transcript_count: int) -> str:
    """Return a localized header describing how many transcripts are included."""

    if transcript_count <= 1:
        return "TRANSCRITO BRUTO DO ÚLTIMO DIA (NA ORDEM CRONOLÓGICA POR DIA):"
    return (
        f"TRANSCRITO BRUTO DOS ÚLTIMOS {transcript_count} DIAS "
        "(NA ORDEM CRONOLÓGICA POR DIA):"
    )


def build_llm_input(
    *,
    group_name: str,
    timezone: tzinfo,
    transcripts: Sequence[tuple[date, str]],
    previous_newsletter: str | None,
    transcript_count: int | None = None,
) -> str:
    """Compose the user prompt sent to Gemini.

    Parameters
    ----------
    transcript_count:
        Optional override for how many days of transcripts are mentioned in the
        header. Defaults to the number of transcript entries provided.
    """

    today_str = datetime.now(timezone).date().isoformat()
    sections: list[str] = [
        f"NOME DO GRUPO: {group_name}",
        f"DATA DE HOJE: {today_str}",
    ]

    if previous_newsletter:
        sections.extend(
            [
                "NEWSLETTER DO DIA ANTERIOR (INCLUA COMO CONTEXTO, NÃO COPIE):",
                "<<<NEWSLETTER_ONTEM_INICIO>>>",
                previous_newsletter.strip(),
                "<<<NEWSLETTER_ONTEM_FIM>>>",
            ]
        )
    else:
        sections.append("NEWSLETTER DO DIA ANTERIOR: NÃO ENCONTRADA")

    header = _format_transcript_section_header(transcript_count or len(transcripts))
    sections.append(header)
    for transcript_date, transcript_text in transcripts:
        sections.extend(
            [
                f"<<<TRANSCRITO_{transcript_date.isoformat()}_INICIO>>>",
                transcript_text.strip() if transcript_text.strip() else "(vazio)",
                f"<<<TRANSCRITO_{transcript_date.isoformat()}_FIM>>>",
            ]
        )

    return "\n\n".join(sections)


def build_system_instruction() -> list[types.Part]:
    """Return the validated system prompt."""

    _require_google_dependency()

    system_text = r"""
Tarefa: produzir uma newsletter diária a partir de um TRANSCRITO BRUTO de conversas de grupo.

Instruções de entrada:
- Você receberá um bloco de texto com mensagens no formato "HH:MM — Remetente: Mensagem" (podem existir variantes).
- O remetente pode vir como nick, número de telefone ou ambos. Links podem aparecer soltos na mensagem.

Objetivo:
- Redigir um relatório diário em português, em estilo de "newsletter", organizado em FIOS (threads), narrado como se o GRUPO fosse UMA ÚNICA MENTE COLETIVA ("nós").
- A newsletter deve SER a voz do grupo, não uma análise SOBRE o grupo.
- Em CADA FRASE do corpo narrativo, colocar o autor entre parênteses imediatamente após a frase. Se houver nick, usar (Nick). Se não houver nick, usar os quatro dígitos finais do telefone, no formato (1234).
- Inserir CADA LINK COMPARTILHADO no ponto exato em que ele é mencionado (link completo, clicável). Não agrupar links no final.
- EXPLICITAR subentendidos, tensões, mudanças de posição e contextos. Não deixar implícito o que está acontecendo em cada momento.
- Não inventar nicks. Não resumir links. Não ocultar mensagens relevantes.

Regras de formatação do relatório:
1) Cabeçalho:
   - Título: "📩 {NOME DO GRUPO} — Diário de {DATA}"
   - Uma linha introdutória, no plural ("nós"), explicando que o dia foi organizado em fios.

2) Estrutura por FIOS (não "arcos", não "seções"):
   - Separar o dia em 4–10 FIOS, cada um com título descritivo e explícito no formato:
     "## Fio X — {título que contextualize claramente o momento/debate/tema}"
   - Cada FIO deve começar com 1-2 frases de CONTEXTO explicando o que está acontecendo naquele momento da nossa mente coletiva, POR QUE aquele tema surgiu, COMO ele se conecta (ou não) ao anterior.
   - Critérios para separar FIOS:
     • Mudança clara de tema OU
     • Intervalos de tempo significativos OU
     • Troca dominante de participantes OU
     • Mudança de tom/intensidade.
   - Dentro de cada FIO, escrever em 1ª pessoa do plural ("nós"), como a mente do grupo, e:
     • CONTEXTUALIZAR: explicar o que está acontecendo, não apenas reportar.
     • EXPLICITAR: tese, antítese, consensos, divergências, tensões não resolvidas.
     • SUBENTENDIDOS: transformar implícitos em explícitos ("Declaramos que…", "Contestamos porque…", "Uma parte de nós temia que…").
     • Citar os links no exato ponto onde foram trazidos, mantendo o link completo.
     • Em CADA FRASE do corpo narrativo, ao final, inserir (Nick) ou (quatro dígitos).

3) Regras de autoria (entre parênteses):
   - Se a linha do remetente tiver nick → usar exatamente esse nick entre parênteses.
   - Se NÃO houver nick, extrair os quatro dígitos finais do número: ex.: +55 11 94529-4774 → (4774).
   - Se houver mídia sem descrição ("<Mídia oculta>"), registrar explicitamente "enviamos mídia sem descrição" (autor entre parênteses).
   - Se a mensagem estiver marcada como editada, pode acrescentar "(editado)" antes do autor.
   - IMPORTANTE: o autor aparece em CADA FRASE de conteúdo substantivo, não apenas uma vez por parágrafo.

4) Tratamento de links:
   - Sempre inserir o link COMPLETO no ponto exato da narrativa em que ele foi mencionado originalmente.
   - Não encurtar, não mover para rodapé, não omitir.
   - Pode haver uma frase curta de contexto sobre o link SE o contexto não for óbvio.

5) Estilo e clareza:
   - Voz: 1ª pessoa do plural ("nós"), IMEDIATA, como se o grupo estivesse narrando a si mesmo.
   - Não usar metalinguagem de planejamento ("vamos estruturar", "o arco se divide", "conectivos"). A newsletter É a narrativa, não uma análise sobre a narrativa.
   - Explicativo e contextual: diga o que cada parte de nós defende e POR QUÊ; diga POR QUÊ as alternativas foram refutadas; diga QUANDO mudamos de assunto e POR QUÊ.
   - Zero mistério: torne explícitos pressupostos, implicações, trade-offs, tensões não resolvidas.
   - Evitar jargão não explicado; quando usar, explique brevemente inline.
   - Tom natural, não excessivamente formal, mas também não casual demais.

6) Epílogo:
   - Fechar com um parágrafo "Epílogo" resumindo:
     • Principais consensos e dissensos do dia.
     • O que ficou em aberto ou não resolvido.
     • Próximos passos implícitos (se existirem) — explicitados.
     • Tensões que permaneceram sem resolução.

7) Qualidade (checklist antes de finalizar):
   - [ ] Cada FIO começa com contexto claro do que está acontecendo.
   - [ ] Fios bem separados por tema/tempo/participantes/tom.
   - [ ] Cada frase substantiva termina com (Nick) ou (quatro dígitos).
   - [ ] Todos os links aparecem no ponto exato em que foram citados.
   - [ ] Subentendidos e tensões foram tornados explícitos.
   - [ ] Sem inventar nicks; sem inventar fatos; sem mover links.
   - [ ] Voz é "nós" narrando nosso próprio dia, não análise externa.
   - [ ] Lacunas no transcrito (se houver) são explicitadas com honestidade.
"""
    return [types.Part.from_text(text=system_text.strip())]


def ensure_directories(config: PipelineConfig) -> None:
    """Ensure required directories exist."""

    config.newsletters_dir.mkdir(parents=True, exist_ok=True)
    config.zips_dir.mkdir(parents=True, exist_ok=True)


def select_recent_archives(
    archives: Sequence[tuple[date, Path]], *, days: int
) -> list[tuple[date, Path]]:
    """Select the most recent archives respecting *days*."""

    if days <= 0:
        raise ValueError("days must be positive")
    return list(archives[-days:]) if len(archives) >= days else list(archives)


def create_client(api_key: str | None = None) -> genai.Client:
    """Instantiate the Gemini client."""

    _require_google_dependency()

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Defina GEMINI_API_KEY no ambiente.")
    return genai.Client(api_key=key)


def generate_newsletter(
    config: PipelineConfig,
    *,
    days: int = 2,
    client: genai.Client | None = None,
) -> PipelineResult:
    """Execute the pipeline and return the resulting metadata."""

    _require_google_dependency()

    ensure_directories(config)

    archives = list_zip_days(config.zips_dir)
    if not archives:
        raise FileNotFoundError(f"Nenhum .zip encontrado em {config.zips_dir.resolve()}")

    selected_archives = select_recent_archives(archives, days=days)
    transcripts: list[tuple[date, str]] = []
    for archive_date, archive_path in selected_archives:
        transcripts.append((archive_date, read_zip_texts(archive_path)))

    today = max(archive_date for archive_date, _ in transcripts)
    previous_path, previous_content = load_previous_newsletter(config.newsletters_dir, today)

    insert_input = build_llm_input(
        group_name=config.group_name,
        timezone=config.timezone,
        transcripts=transcripts,
        previous_newsletter=previous_content,
    )

    llm_client = client or create_client()
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=insert_input)],
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=-1),
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ],
        system_instruction=build_system_instruction(),
    )

    output_lines: list[str] = []
    for chunk in llm_client.models.generate_content_stream(
        model=config.model,
        contents=contents,
        config=generate_content_config,
    ):
        if chunk.text:
            output_lines.append(chunk.text)

    newsletter_text = "".join(output_lines).strip()
    output_path = config.newsletters_dir / f"{today.isoformat()}.md"
    output_path.write_text(newsletter_text, encoding="utf-8")

    return PipelineResult(
        output_path=output_path,
        processed_dates=[archive_date for archive_date, _ in transcripts],
        previous_newsletter_path=previous_path,
        previous_newsletter_found=previous_content is not None,
    )


__all__ = [
    "PipelineResult",
    "create_client",
    "generate_newsletter",
]
