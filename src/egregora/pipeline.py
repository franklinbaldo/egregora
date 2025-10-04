"""Core newsletter generation pipeline."""

from __future__ import annotations

import os
import re
import zipfile
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any, Sequence

import logging

try:  # pragma: no cover - executed only when dependency is missing
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows importing without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from .anonymizer import Anonymizer
from .config import PipelineConfig
from .media_extractor import MediaExtractor, MediaFile

DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _emit(
    message: str,
    *,
    logger: logging.Logger | None = None,
    batch_mode: bool = False,
    level: str = "info",
) -> None:
    """Emit a log message respecting batch execution preferences."""

    if logger is not None:
        log_func = getattr(logger, level, logger.info)
        log_func(message)
    elif not batch_mode:
        print(message)


TRANSCRIPT_PATTERNS = [
    re.compile(
        r"^(?P<prefix>\d{1,2}:\d{2}\s[-–—]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(
        r"^(?P<prefix>\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s[-–—]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(
        r"^(?P<prefix>\[\d{1,2}:\d{2}:\d{2}\]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(
        r"^(?P<prefix>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+[-–—]\s+)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
]

def _anonymize_transcript_line(
    line: str,
    *,
    anonymize: bool,
    format: str = "human",
) -> str:
    """Return ``line`` with the author anonymized when enabled."""

    if not anonymize:
        return line

    for pattern in TRANSCRIPT_PATTERNS:
        match = pattern.match(line)
        if not match:
            continue

        prefix = match.group("prefix")
        author = match.group("author").strip()
        separator = match.group("separator")
        message = match.group("message")

        if author:
            anonymized = Anonymizer.anonymize_author(author, format)
        else:
            anonymized = author

        return f"{prefix}{anonymized}{separator}{message}"

    return line


def _prepare_transcripts(
    transcripts: Sequence[tuple[date, str]],
    config: PipelineConfig,
    *,
    logger: logging.Logger | None = None,
    batch_mode: bool = False,
) -> list[tuple[date, str]]:
    """Return transcripts with authors anonymized when enabled."""

    sanitized: list[tuple[date, str]] = []
    anonymized_authors: set[str] = set()
    processed_lines = 0

    for transcript_date, raw_text in transcripts:
        if not config.anonymization.enabled or not raw_text:
            sanitized.append((transcript_date, raw_text))
            continue

        processed_parts: list[str] = []
        for raw_line in raw_text.splitlines(keepends=True):
            if raw_line.endswith("\n"):
                line = raw_line[:-1]
                newline = "\n"
            else:
                line = raw_line
                newline = ""

            anonymized = _anonymize_transcript_line(
                line,
                anonymize=config.anonymization.enabled,
                format=config.anonymization.output_format,
            )
            processed_parts.append(anonymized + newline)

            processed_lines += 1
            for pattern in TRANSCRIPT_PATTERNS:
                match = pattern.match(line)
                if not match:
                    continue

                author = match.group("author").strip()
                if author:
                    anonymized_authors.add(author)
                break

        sanitized.append((transcript_date, "".join(processed_parts)))

    if config.anonymization.enabled:
        _emit(
            "[Anonimização] "
            f"{len(anonymized_authors)} remetentes anonimizados em {processed_lines} linhas.",
            logger=logger,
            batch_mode=batch_mode,
        )

    return sanitized


def _prepare_transcripts_sample(
    transcripts: Sequence[tuple[date, str]],
    *,
    max_chars: int,
) -> str:
    """Concatenate recent transcripts limited to ``max_chars`` characters."""

    if max_chars <= 0:
        return ""

    ordered = sorted(transcripts, key=lambda item: item[0], reverse=True)
    collected: list[str] = []
    remaining = max_chars

    for _, text in ordered:
        snippet = text.strip()
        if not snippet:
            continue

        if len(snippet) > remaining:
            snippet = snippet[:remaining]
        collected.append(snippet)
        remaining -= len(snippet)
        if remaining <= 0:
            break

    return "\n\n".join(collected).strip()


def _require_google_dependency() -> None:
    """Ensure the optional google-genai dependency is available."""

    if genai is None or types is None:
        raise RuntimeError(
            "A dependência opcional 'google-genai' não está instalada. "
            "Instale-a para gerar newsletters (ex.: `pip install google-genai`)."
        )


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


def read_zip_texts_and_media(
    zippath: Path,
    *,
    archive_date: date | None = None,
    media_dir: Path | None = None,
) -> tuple[str, dict[str, MediaFile]]:
    """Read texts from *zippath* and optionally extract media files."""

    extractor: MediaExtractor | None = None
    media_files: dict[str, MediaFile] = {}

    if archive_date is not None and media_dir is not None:
        extractor = MediaExtractor(media_dir)
        media_files = extractor.extract_media_from_zip(zippath, archive_date)

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

    transcript = "\n".join(chunks).strip()
    if extractor is not None and transcript:
        transcript = MediaExtractor.replace_media_references(transcript, media_files)

    return transcript, media_files


def read_zip_texts(
    zippath: Path,
    *,
    archive_date: date | None = None,
    media_dir: Path | None = None,
) -> str:
    """Compatibility wrapper returning only the transcript text."""

    transcript, _ = read_zip_texts_and_media(
        zippath,
        archive_date=archive_date,
        media_dir=media_dir,
    )
    return transcript


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
    enrichment_section: str | None = None,
    rag_context: str | None = None,
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

    if enrichment_section:
        sections.extend(
            [
                "CONTEXTOS ENRIQUECIDOS DOS LINKS COMPARTILHADOS:",
                enrichment_section,
            ]
        )

    if rag_context:
        sections.extend(
            [
                "CONTEXTOS HISTÓRICOS DE NEWSLETTERS RELEVANTES:",
                rag_context,
            ]
        )

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


def build_system_instruction(has_group_tags: bool = False) -> list[types.Part]:
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

🔒 PRIVACIDADE — INSTRUÇÕES CRÍTICAS:
- Utilize APENAS os identificadores anônimos fornecidos (Member-XXXX, etc.).
- Nunca repita nomes próprios, telefones completos ou e-mails mencionados NO CONTEÚDO das mensagens.
- Ao referenciar alguém citado no conteúdo mas sem identificador anônimo, generalize ("um membro", "uma pessoa do grupo").
- Preserve o sentido original enquanto remove detalhes de contato ou identificação direta.

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
    
    if has_group_tags:
        system_text += """

⚠️ MENSAGENS TAGUEADAS:
- Este grupo agrega múltiplas fontes/grupos
- Tags indicam origem: [Grupo], 🌎, etc
- Mencione origem quando RELEVANTE para o contexto
- Trate como conversa UNIFICADA de uma mente coletiva
- Não force menção das tags em todo parágrafo
"""

    return [types.Part.from_text(text=system_text.strip())]


def ensure_directories(config: PipelineConfig) -> None:
    """Ensure required directories exist."""

    config.newsletters_dir.mkdir(parents=True, exist_ok=True)
    config.zips_dir.mkdir(parents=True, exist_ok=True)
    config.media_dir.mkdir(parents=True, exist_ok=True)


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


__all__ = [
    "build_llm_input",
    "build_system_instruction",
    "create_client",
    "ensure_directories",
    "find_date_in_name",
    "list_zip_days",
    "load_previous_newsletter",
    "read_zip_texts",
    "read_zip_texts_and_media",
    "select_recent_archives",
    "_anonymize_transcript_line",
    "_prepare_transcripts",
    "_prepare_transcripts_sample",
]
