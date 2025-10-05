"""Core newsletter generation pipeline."""

from __future__ import annotations

import os
import re
import zipfile
import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Awaitable, List, Sequence, TypeVar

try:  # pragma: no cover - executed only when dependency is missing
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
except ModuleNotFoundError:  # pragma: no cover - allows importing without dependency
    genai = None  # type: ignore
    GenerationConfig = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from mcp.client import Client, StdioServerParameters
except ModuleNotFoundError:  # pragma: no cover - allows running without MCP
    Client = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]

from .anonymizer import Anonymizer, FormatType
from .cache_manager import CacheManager
from .config import PipelineConfig
from .mcp_server.tools import format_search_hits
from .rag.core import NewsletterRAG
from .rag.query_gen import QueryGenerator
from .enrichment import ContentEnricher, EnrichmentResult

DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


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

REVIEW_SYSTEM_PROMPT = r"""
Você é um revisor de privacidade. Seu papel é garantir que nenhuma informação
pessoal direta permaneça na newsletter. Remova ou generalize:
- Nomes próprios de pessoas físicas.
- Números de telefone ou outros identificadores de contato.
- E-mails ou endereços.

Não invente fatos novos e preserve o sentido do texto. Se o conteúdo já estiver
adequado, devolva exatamente o mesmo texto.
"""


def _anonymize_transcript_line(
    line: str, *, anonymize: bool, output_format: FormatType
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
            anonymized = Anonymizer.anonymize_author(author, format=output_format)
        else:
            anonymized = author

        return f"{prefix}{anonymized}{separator}{message}"

    return line


def _prepare_transcripts(
    transcripts: Sequence[tuple[date, str]],
    config: PipelineConfig,
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
                output_format=config.anonymization.output_format,
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
        print(
            "[Anonimização] "
            f"{len(anonymized_authors)} remetentes anonimizados em {processed_lines} linhas. "
            f"Formato: {config.anonymization.output_format}."
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


def _rag_cache_directory(config: PipelineConfig) -> Path:
    base = config.cache.cache_dir if config.cache.enabled else Path("cache")
    return (base / "rag").expanduser()


def _collect_rag_context_local(
    config: PipelineConfig, transcripts_sample: str
) -> str | None:
    rag = NewsletterRAG(
        newsletters_dir=config.newsletters_dir,
        cache_dir=_rag_cache_directory(config),
        config=config.rag,
    )
    rag.load_index()

    query_generator = QueryGenerator(config.rag)
    query_data = query_generator.generate(transcripts_sample)
    hits = rag.search(
        query=query_data.search_query,
        top_k=config.rag.top_k,
        min_similarity=config.rag.min_similarity,
        exclude_recent_days=config.rag.exclude_recent_days,
    )

    if not hits:
        return None

    return format_search_hits(hits)


def _extract_query_from_markdown(markdown: str) -> str:
    capture = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if capture:
            if stripped:
                return stripped
            continue
        if stripped.lower().startswith("**query de busca"):
            capture = True
    return ""


T_co = TypeVar("T_co")


def _run_async(coro: Awaitable[T_co]) -> T_co:
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "event loop" in str(exc).lower():
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        raise


async def _collect_rag_context_via_mcp(
    config: PipelineConfig, transcripts_sample: str
) -> str | None:
    if Client is None or StdioServerParameters is None:
        raise RuntimeError("A dependência opcional 'mcp' não está instalada.")

    server_params = StdioServerParameters(
        command=config.rag.mcp_command,
        args=list(config.rag.mcp_args),
    )

    async with Client() as client:
        await client.connect(server_params)

        query_parts = await client.call_tool(
            "generate_search_query",
            arguments={"transcripts": transcripts_sample},
        )
        query_markdown = "".join(
            part.text for part in query_parts if hasattr(part, "text") and part.text
        )
        search_query = _extract_query_from_markdown(query_markdown)
        if not search_query:
            search_query = transcripts_sample[:200]

        search_parts = await client.call_tool(
            "search_newsletters",
            arguments={
                "query": search_query,
                "top_k": config.rag.top_k,
                "min_similarity": config.rag.min_similarity,
                "exclude_recent_days": config.rag.exclude_recent_days,
            },
        )

        return "".join(
            part.text for part in search_parts if hasattr(part, "text") and part.text
        ).strip()


def _collect_rag_context(config: PipelineConfig, transcripts_sample: str) -> str | None:
    if not transcripts_sample.strip():
        return None

    if config.rag.use_mcp:
        try:
            context = _run_async(_collect_rag_context_via_mcp(config, transcripts_sample))
            if context:
                return context
        except Exception as exc:
            print(
                f"[Aviso] RAG via MCP indisponível: {exc}. Tentando fallback local."
            )

    return _collect_rag_context_local(config, transcripts_sample)


def _run_privacy_review(
    client: genai.Client,
    *,
    model: str,
    newsletter_text: str,
) -> str:
    """Request a second-pass privacy review from the configured LLM."""

    review_prompt = (
        "Revise a newsletter e remova nomes próprios, números de telefone, "
        "endereços de e-mail ou outras referências diretas a contato. "
        "Generalize informações sensíveis quando necessário. Se nada "
        "precisar ser alterado, devolva o texto exatamente como recebido.\n\n"
        "<<<NEWSLETTER_ORIGINAL>>>\n"
        f"{newsletter_text}\n"
        "<<<FIM>>>"
    )

    contents = [
        genai.Content(
            role="user",
            parts=[genai.Part.from_text(text=review_prompt)],
        )
    ]

    review_config = GenerationConfig()
    system_instruction = genai.Part.from_text(text=REVIEW_SYSTEM_PROMPT.strip())

    output_lines: list[str] = []
    for chunk in client.generate_content(
        model=model,
        contents=contents,
        generation_config=review_config,
        system_instruction=system_instruction,
        stream=True
    ):
        if chunk.text:
            output_lines.append(chunk.text)

    reviewed = "".join(output_lines).strip()
    return reviewed or newsletter_text


def _require_google_dependency() -> None:
    """Ensure the optional google-genai dependency is available."""

    if genai is None:
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
    enrichment: EnrichmentResult | None


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


def build_system_instruction() -> list[genai.Part]:
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
- Utilize APENAS os identificadores anônimos fornecidos (User-XXXX, Member-XXXX, etc.).
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
    return [genai.Part.from_text(text=system_text.strip())]


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
    raw_transcripts: list[tuple[date, str]] = []
    for archive_date, archive_path in selected_archives:
        raw_transcripts.append((archive_date, read_zip_texts(archive_path)))

    sanitized_transcripts = _prepare_transcripts(raw_transcripts, config)

    today = max(archive_date for archive_date, _ in sanitized_transcripts)
    previous_path, previous_content = load_previous_newsletter(
        config.newsletters_dir, today
    )

    llm_client = client or create_client()

    rag_context: str | None = None
    if config.rag.enabled:
        transcripts_sample = _prepare_transcripts_sample(
            sanitized_transcripts,
            max_chars=config.rag.max_context_chars * 3,
        )
        if transcripts_sample:
            try:
                rag_context = _collect_rag_context(config, transcripts_sample)
                if rag_context:
                    print("[RAG] Contexto histórico recuperado.")
            except Exception as exc:
                print(f"[Aviso] RAG indisponível: {exc}")

    cache_manager: CacheManager | None = None
    if config.cache.enabled:
        cache_manager = CacheManager(config.cache.cache_dir)
        if config.cache.auto_cleanup_days is not None:
            cache_manager.cleanup_old_entries(config.cache.auto_cleanup_days)
        if config.cache.max_disk_mb is not None:
            stats = cache_manager.get_stats()
            if stats.get("disk_usage_mb", 0.0) > config.cache.max_disk_mb:
                print(
                    "[Aviso] Cache excedeu o limite configurado; considere executar"
                    " uma limpeza."
                )

    enrichment_result: EnrichmentResult | None = None
    enrichment_section: str | None = None
    if config.enrichment.enabled:
        enricher = ContentEnricher(
            config.enrichment, cache_manager=cache_manager
        )
        try:
            enrichment_result = asyncio.run(
                enricher.enrich(sanitized_transcripts, client=llm_client)
            )
        except RuntimeError as exc:
            if "event loop" in str(exc).lower():
                loop = asyncio.new_event_loop()
                try:
                    enrichment_result = loop.run_until_complete(
                        enricher.enrich(sanitized_transcripts, client=llm_client)
                    )
                finally:
                    loop.close()
            else:
                print(f"[Aviso] Enriquecimento não executado: {exc}")
        except Exception as exc:  # pragma: no cover - depende de rede/modelo
            print(f"[Aviso] Enriquecimento falhou: {exc}")

        if enrichment_result:
            enrichment_section = enrichment_result.format_for_prompt(
                config.enrichment.relevance_threshold
            )
            relevant_count = len(
                enrichment_result.relevant_items(
                    config.enrichment.relevance_threshold
                )
            )
            total_count = len(enrichment_result.items)
            print(
                f"[Enriquecimento] {relevant_count}/{total_count} itens relevantes "
                f"processados em {enrichment_result.duration_seconds:.1f}s."
            )
            for error in enrichment_result.errors:
                print(f"[Enriquecimento:falha] {error}")

    insert_input = build_llm_input(
        group_name=config.group_name,
        timezone=config.timezone,
        transcripts=sanitized_transcripts,
        previous_newsletter=previous_content,
        enrichment_section=enrichment_section,
        rag_context=rag_context,
    )

    contents = [
        genai.Content(
            role="user",
            parts=[genai.Part.from_text(text=insert_input)],
        ),
    ]

    generate_content_config = GenerationConfig()
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    system_instruction = build_system_instruction()

    output_lines: list[str] = []
    for chunk in llm_client.generate_content(
        model=config.model,
        contents=contents,
        generation_config=generate_content_config,
        system_instruction=system_instruction,
        safety_settings=safety_settings,
        stream=True
    ):
        if chunk.text:
            output_lines.append(chunk.text)

    newsletter_text = "".join(output_lines).strip()
    output_path = config.newsletters_dir / f"{today.isoformat()}.md"

    if config.privacy.double_check_newsletter:
        review_model = config.privacy.review_model or config.model
        revised = _run_privacy_review(
            llm_client,
            model=review_model,
            newsletter_text=newsletter_text,
        )
        if revised != newsletter_text:
            print("[Privacidade] Revisão adicional removeu dados sensíveis.")
            newsletter_text = revised
        else:
            print("[Privacidade] Revisão adicional não encontrou ajustes.")

    output_path.write_text(newsletter_text, encoding="utf-8")

    return PipelineResult(
        output_path=output_path,
        processed_dates=[archive_date for archive_date, _ in sanitized_transcripts],
        previous_newsletter_path=previous_path,
        previous_newsletter_found=previous_content is not None,
        enrichment=enrichment_result,
    )


__all__ = [
    "PipelineResult",
    "create_client",
    "generate_newsletter",
]