O usuário quer que eu reescreva o plano completo usando pandas como a abordagem principal para manipular as conversas. Vou criar um plano limpo e completo que incorpora pandas desde o início.

O plano deve:
1. Manter os princípios de auto-discovery
2. Usar pandas para parse, merge e manipulação
3. Simplificar a arquitetura
4. Manter grupos virtuais como conceito
5. Ser mais conciso e direto

Vou estruturar em fases claras com código prático.

# 🎯 Plano Completo: Auto-Discovery + Grupos Virtuais com Pandas

## Visão Geral

```
ZIPs → DataFrame → Merge (opcional) → Transcrito → Newsletter
  ↓        ↓            ↓                  ↓
Auto    Parse     Concat + Sort      string     LLM
Detect  Msgs      + Tag Groups       lines
```

**Princípio Central:**
- Tudo é DataFrame até virar transcrito de texto
- Grupos virtuais = DataFrames concatenados com coluna de tag
- Processamento idêntico para grupos reais e virtuais

## 📐 Arquitetura

```
src/egregora/
├── models.py          # Dataclasses (WhatsAppExport, GroupSource, MergeConfig)
├── discovery.py       # Auto-detect grupos dos ZIPs
├── parser.py          # ZIP → DataFrame
├── merger.py          # Merge DataFrames + tags
├── transcript.py      # DataFrame → texto
├── processor.py       # Orquestrador principal
├── config.py          # PipelineConfig
├── analytics.py       # Análises com pandas (bonus)
└── __main__.py        # CLI
```

## 📊 Schema do DataFrame

```python
# Cada row = uma mensagem

Colunas:
- timestamp: datetime      # 2025-10-01 10:30:00
- date: date              # 2025-10-01
- time: str               # "10:30"
- author: str             # "User-A1B2" (já anonimizado)
- message: str            # "Bom dia pessoal!"
- group_slug: str         # "rc-latam"
- group_name: str         # "RC LatAm"
- original_line: str      # "10:30 — User-A1B2: Bom dia pessoal!"
- tagged_line: str        # "10:30 — User-A1B2 🌎: Bom dia pessoal!" (só para merges)
```

---

## 🔧 Implementação

### **FASE 1: Models & Discovery** (1 hora)

```python
# src/egregora/models.py

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal


@dataclass(slots=True)
class WhatsAppExport:
    """Metadados extraídos de um ZIP do WhatsApp."""
    
    zip_path: Path
    group_name: str          # "RC LatAm"
    group_slug: str          # "rc-latam"
    export_date: date        # 2025-10-01
    chat_file: str           # "Conversa do WhatsApp com RC LatAm.txt"
    media_files: list[str]   # ["IMG-001.jpg", ...]


@dataclass(slots=True)
class MergeConfig:
    """Configuração de merge de grupos."""
    
    name: str                                                    # "RC Americas"
    source_groups: list[str]                                     # ["rc-latam", "rc-brasil"]
    tag_style: Literal["emoji", "brackets", "prefix"] = "emoji"
    group_emojis: dict[str, str] = field(default_factory=dict)   # {"rc-latam": "🌎"}
    model_override: str | None = None


@dataclass(slots=True)
class GroupSource:
    """
    Fonte para gerar newsletter.
    Pode ser real (1 grupo) ou virtual (merge de N grupos).
    """
    
    slug: str                          # "rc-latam" ou "rc-americas"
    name: str                          # "RC LatAm" ou "RC Americas"
    exports: list[WhatsAppExport]      # Exports deste source
    is_virtual: bool = False
    merge_config: MergeConfig | None = None
```

```python
# src/egregora/discovery.py

from pathlib import Path
from datetime import date, datetime
from collections import defaultdict
import re
import zipfile
import unicodedata
import logging

from .models import WhatsAppExport

logger = logging.getLogger(__name__)


def discover_groups(zips_dir: Path) -> dict[str, list[WhatsAppExport]]:
    """
    Escaneia ZIPs e retorna grupos descobertos.
    
    Returns:
        {slug: [exports]} ordenados por data
    """
    
    groups = defaultdict(list)
    
    for zip_path in sorted(zips_dir.glob("*.zip")):
        try:
            export = _extract_metadata(zip_path)
            groups[export.group_slug].append(export)
        except Exception as e:
            logger.warning(f"Skipping {zip_path.name}: {e}")
            continue
    
    # Ordena exports por data
    for slug in groups:
        groups[slug].sort(key=lambda e: e.export_date)
    
    return dict(groups)


def _extract_metadata(zip_path: Path) -> WhatsAppExport:
    """Extrai metadados de um ZIP."""
    
    with zipfile.ZipFile(zip_path) as zf:
        # Acha arquivo .txt
        txt_files = [
            f for f in zf.namelist() 
            if f.endswith('.txt') and not f.startswith('__MACOSX')
        ]
        
        if not txt_files:
            raise ValueError("No chat file found")
        
        chat_file = txt_files[0]
        
        # Extrai nome do grupo
        group_name = _extract_group_name(chat_file)
        group_slug = _slugify(group_name)
        
        # Extrai data
        export_date = _extract_date(zip_path, zf, chat_file)
        
        # Lista mídias
        media_files = [f for f in zf.namelist() if f != chat_file]
        
        return WhatsAppExport(
            zip_path=zip_path,
            group_name=group_name,
            group_slug=group_slug,
            export_date=export_date,
            chat_file=chat_file,
            media_files=media_files,
        )


def _extract_group_name(filename: str) -> str:
    """
    Extrai nome do grupo do arquivo .txt interno.
    Suporta PT, EN, ES.
    """
    
    patterns = [
        r'Conversa do WhatsApp com (.+?)\.txt',      # PT
        r'WhatsApp Chat with (.+?)\.txt',            # EN
        r'Chat de WhatsApp con (.+?)\.txt',          # ES
        r'Conversación de WhatsApp con (.+?)\.txt',  # ES alt
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Fallback
    return filename.replace('.txt', '').strip()


def _slugify(text: str) -> str:
    """Converte para slug filesystem-safe."""
    
    # Remove acentos
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Lowercase, remove especiais, substitui espaços
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    
    return text.strip('-')


def _extract_date(zip_path: Path, zf: zipfile.ZipFile, chat_file: str) -> date:
    """Extrai data do export (ZIP name > conteúdo > mtime)."""
    
    # 1. Do nome do ZIP
    match = re.search(r'(\d{4}-\d{2}-\d{2})', zip_path.name)
    if match:
        return date.fromisoformat(match.group(1))
    
    # 2. Da primeira mensagem
    try:
        with zf.open(chat_file) as f:
            for _ in range(20):  # Primeiras 20 linhas
                line = f.readline().decode('utf-8', errors='ignore')
                match = re.search(r'(\d{2})/(\d{2})/(\d{4}|\d{2})', line)
                if match:
                    day, month, year = match.groups()
                    year = int(year)
                    if year < 100:
                        year += 2000
                    return date(year, int(month), int(day))
    except Exception:
        pass
    
    # 3. Fallback: mtime do arquivo
    timestamp = zip_path.stat().st_mtime
    return datetime.fromtimestamp(timestamp).date()
```

### **FASE 2: Parser (ZIP → DataFrame)** (2 horas)

```python
# src/egregora/parser.py

import re
import zipfile
from datetime import datetime, date
from pathlib import Path
import pandas as pd
import logging

from .models import WhatsAppExport

logger = logging.getLogger(__name__)


def parse_export(export: WhatsAppExport) -> pd.DataFrame:
    """
    Parse um export para DataFrame.
    
    Returns:
        DataFrame com colunas: timestamp, date, time, author, message,
                               group_slug, group_name, original_line
    """
    
    # Lê conteúdo
    with zipfile.ZipFile(export.zip_path) as zf:
        with zf.open(export.chat_file) as f:
            content = f.read().decode('utf-8', errors='ignore')
    
    # Parse mensagens
    rows = _parse_messages(content, export)
    
    if not rows:
        return pd.DataFrame()
    
    # Cria DataFrame
    df = pd.DataFrame(rows)
    
    # Converte tipos
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = pd.to_datetime(df['date']).dt.date
    
    return df


def parse_multiple(exports: list[WhatsAppExport]) -> pd.DataFrame:
    """
    Parse múltiplos exports e concatena ordenado.
    """
    
    dfs = []
    
    for export in exports:
        df = parse_export(export)
        if not df.empty:
            dfs.append(df)
    
    if not dfs:
        return pd.DataFrame()
    
    # Concatena e ordena por timestamp
    merged = pd.concat(dfs, ignore_index=True)
    merged = merged.sort_values('timestamp').reset_index(drop=True)
    
    return merged


def _parse_messages(content: str, export: WhatsAppExport) -> list[dict]:
    """Parse mensagens do conteúdo."""
    
    # Padrões WhatsApp (com/sem data na linha)
    # Com data: "01/10/2025, 10:30 - Author: Message"
    # Sem data: "10:30 - Author: Message"
    
    pattern = re.compile(
        r'^(?:(\d{2}/\d{2}/\d{4}),?\s*)?'  # Data opcional
        r'(\d{1,2}:\d{2})'                  # Hora
        r'\s*[—\-]\s*'                      # Separador
        r'([^:]+?):\s*'                     # Autor
        r'(.+)$',                           # Mensagem
        re.MULTILINE
    )
    
    rows = []
    
    for line in content.split('\n'):
        match = pattern.match(line)
        if not match:
            continue
        
        date_str, time_str, author, message = match.groups()
        
        # Determina data
        if date_str:
            msg_date = datetime.strptime(date_str, "%d/%m/%Y").date()
        else:
            msg_date = export.export_date
        
        # Parse tempo
        try:
            msg_time = datetime.strptime(time_str, "%H:%M").time()
            timestamp = datetime.combine(msg_date, msg_time)
        except ValueError:
            continue
        
        rows.append({
            'timestamp': timestamp,
            'date': msg_date,
            'time': time_str,
            'author': author.strip(),
            'message': message.strip(),
            'group_slug': export.group_slug,
            'group_name': export.group_name,
            'original_line': line.strip(),
        })
    
    return rows
```

### **FASE 3: Merger (DataFrames + Tags)** (1 hora)

```python
# src/egregora/merger.py

import pandas as pd
from typing import Literal

from .models import WhatsAppExport, MergeConfig, GroupSource
from .parser import parse_multiple


def create_virtual_groups(
    real_groups: dict[str, list[WhatsAppExport]],
    merge_configs: dict[str, MergeConfig],
) -> dict[str, GroupSource]:
    """Cria grupos virtuais a partir de configurações."""
    
    virtual = {}
    
    for slug, config in merge_configs.items():
        # Coleta exports dos grupos fonte
        merged_exports = []
        
        for source_slug in config.source_groups:
            exports = real_groups.get(source_slug, [])
            if not exports:
                import logging
                logging.warning(f"Virtual group '{slug}': source '{source_slug}' not found")
                continue
            merged_exports.extend(exports)
        
        if not merged_exports:
            continue
        
        # Ordena por data
        merged_exports.sort(key=lambda e: e.export_date)
        
        virtual[slug] = GroupSource(
            slug=slug,
            name=config.name,
            exports=merged_exports,
            is_virtual=True,
            merge_config=config,
        )
    
    return virtual


def merge_with_tags(
    exports: list[WhatsAppExport],
    merge_config: MergeConfig,
) -> pd.DataFrame:
    """
    Mescla exports em DataFrame único com tags.
    
    Returns:
        DataFrame com coluna adicional 'tagged_line'
    """
    
    # Parse todos
    df = parse_multiple(exports)
    
    if df.empty:
        return df
    
    # Adiciona tagged_line
    df['tagged_line'] = df.apply(
        lambda row: _add_tag(
            row['time'],
            row['author'],
            row['message'],
            row['group_slug'],
            row['group_name'],
            merge_config,
        ),
        axis=1
    )
    
    return df


def _add_tag(
    time: str,
    author: str,
    message: str,
    group_slug: str,
    group_name: str,
    config: MergeConfig,
) -> str:
    """Adiciona tag de grupo."""
    
    if config.tag_style == "emoji":
        emoji = config.group_emojis.get(group_slug, "📱")
        return f"{time} — {author} {emoji}: {message}"
    
    elif config.tag_style == "prefix":
        return f"{time} — [{group_name}] {author}: {message}"
    
    else:  # brackets
        return f"{time} — {author} [{group_name}]: {message}"


def get_merge_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Estatísticas de merge por grupo."""
    
    return (
        df.groupby(['group_slug', 'group_name'])
        .size()
        .reset_index(name='message_count')
        .sort_values('message_count', ascending=False)
    )
```

### **FASE 4: Transcript (DataFrame → Text)** (30 min)

```python
# src/egregora/transcript.py

from datetime import date
import pandas as pd

from .models import GroupSource
from .parser import parse_multiple
from .merger import merge_with_tags


def extract_transcript(source: GroupSource, target_date: date) -> str:
    """
    Extrai transcrito para uma data.
    Funciona para reais E virtuais!
    """
    
    if source.is_virtual:
        # Virtual: merge com tags
        df = merge_with_tags(source.exports, source.merge_config)
        
        # Filtra data
        df_day = df[df['date'] == target_date]
        
        if df_day.empty:
            return ""
        
        # Retorna linhas tagueadas
        return '\n'.join(df_day['tagged_line'].tolist())
    
    else:
        # Real: parse simples
        exports_for_date = [e for e in source.exports if e.export_date == target_date]
        
        if not exports_for_date:
            return ""
        
        df = parse_multiple(exports_for_date)
        
        if df.empty:
            return ""
        
        # Retorna linhas originais
        return '\n'.join(df['original_line'].tolist())


def get_stats_for_date(source: GroupSource, target_date: date) -> dict:
    """Estatísticas de um dia."""
    
    from .parser import parse_multiple
    from .merger import merge_with_tags
    
    if source.is_virtual:
        df = merge_with_tags(source.exports, source.merge_config)
    else:
        df = parse_multiple(source.exports)
    
    df_day = df[df['date'] == target_date]
    
    if df_day.empty:
        return {}
    
    return {
        'message_count': len(df_day),
        'participant_count': df_day['author'].nunique(),
        'first_message': df_day['timestamp'].min(),
        'last_message': df_day['timestamp'].max(),
    }
```

### **FASE 5: Config** (1 hora)

```python
# src/egregora/config.py

from dataclasses import dataclass, field
from pathlib import Path
from datetime import tzinfo
from zoneinfo import ZoneInfo

from .models import MergeConfig


DEFAULT_MODEL = "gemini-flash-lite-latest"
DEFAULT_TIMEZONE = "America/Porto_Velho"


@dataclass(slots=True)
class EnrichmentConfig:
    enabled: bool = True
    enrichment_model: str = "gemini-2.0-flash-exp"
    max_links: int = 50
    # ... outros campos


@dataclass(slots=True)
class CacheConfig:
    enabled: bool = True
    cache_dir: Path = Path("cache")
    auto_cleanup_days: int | None = 90
    # ... outros campos


@dataclass(slots=True)
class AnonymizationConfig:
    enabled: bool = True
    output_format: str = "human"


@dataclass(slots=True)
class RAGConfig:
    enabled: bool = False
    # ... campos


@dataclass(slots=True)
class PipelineConfig:
    """Configuração completa."""
    
    # Diretórios
    zips_dir: Path
    newsletters_dir: Path
    media_dir: Path
    
    # LLM
    model: str
    timezone: tzinfo
    
    # Subsistemas
    enrichment: EnrichmentConfig
    cache: CacheConfig
    anonymization: AnonymizationConfig
    rag: RAGConfig
    
    # Merges (grupos virtuais)
    merges: dict[str, MergeConfig] = field(default_factory=dict)
    
    # Se True, pula grupos reais que estão em merges
    skip_real_if_in_virtual: bool = True
    
    @classmethod
    def from_toml(cls, toml_path: Path) -> "PipelineConfig":
        """Carrega de arquivo TOML."""
        import tomllib
        
        with open(toml_path, 'rb') as f:
            data = tomllib.load(f)
        
        # Parse merges
        merges = {}
        for slug, merge_data in data.get('merges', {}).items():
            merges[slug] = MergeConfig(
                name=merge_data['name'],
                source_groups=merge_data['groups'],
                tag_style=merge_data.get('tag_style', 'emoji'),
                group_emojis=merge_data.get('emojis', {}),
                model_override=merge_data.get('model'),
            )
        
        # Parse resto
        dirs = data.get('directories', {})
        pipeline = data.get('pipeline', {})
        
        return cls(
            zips_dir=Path(dirs.get('zips_dir', 'data/whatsapp_zips')),
            newsletters_dir=Path(dirs.get('newsletters_dir', 'newsletters')),
            media_dir=Path(dirs.get('media_dir', 'media')),
            model=pipeline.get('model', DEFAULT_MODEL),
            timezone=ZoneInfo(pipeline.get('timezone', DEFAULT_TIMEZONE)),
            enrichment=EnrichmentConfig(**data.get('enrichment', {})),
            cache=CacheConfig(**data.get('cache', {})),
            anonymization=AnonymizationConfig(**data.get('anonymization', {})),
            rag=RAGConfig(**data.get('rag', {})),
            merges=merges,
            skip_real_if_in_virtual=pipeline.get('skip_real_if_in_virtual', True),
        )
    
    @classmethod
    def with_defaults(cls, **overrides) -> "PipelineConfig":
        """Cria com defaults."""
        
        return cls(
            zips_dir=overrides.get('zips_dir', Path('data/whatsapp_zips')),
            newsletters_dir=overrides.get('newsletters_dir', Path('newsletters')),
            media_dir=overrides.get('media_dir', Path('media')),
            model=overrides.get('model', DEFAULT_MODEL),
            timezone=overrides.get('timezone', ZoneInfo(DEFAULT_TIMEZONE)),
            enrichment=overrides.get('enrichment', EnrichmentConfig()),
            cache=overrides.get('cache', CacheConfig()),
            anonymization=overrides.get('anonymization', AnonymizationConfig()),
            rag=overrides.get('rag', RAGConfig()),
            merges=overrides.get('merges', {}),
            skip_real_if_in_virtual=overrides.get('skip_real_if_in_virtual', True),
        )
```

**Exemplo egregora.toml:**

```toml
[pipeline]
model = "gemini-flash-lite-latest"
timezone = "America/Porto_Velho"
skip_real_if_in_virtual = true

[directories]
zips_dir = "data/whatsapp_zips"
newsletters_dir = "newsletters"

# Grupos virtuais
[merges.rc-americas]
name = "RC Americas"
groups = ["rc-latam", "rc-brasil", "rc-mexico"]
tag_style = "emoji"
emojis = { rc-latam = "🌎", rc-brasil = "🇧🇷", rc-mexico = "🇲🇽" }

[merges.tech-all]
name = "Tech Ecosystem"
groups = ["tech-discussion", "tech-jobs"]
tag_style = "brackets"
model = "gemini-2.0-flash-exp"

[enrichment]
enabled = true

[cache]
enabled = true
```

### **FASE 6: Processor** (2 horas)

```python
# src/egregora/processor.py

from pathlib import Path
from datetime import date
import logging

from .discovery import discover_groups
from .merger import create_virtual_groups, get_merge_stats
from .transcript import extract_transcript, get_stats_for_date
from .models import GroupSource, WhatsAppExport
from .config import PipelineConfig
from .parser import parse_multiple

logger = logging.getLogger(__name__)


class UnifiedProcessor:
    """Processador unificado com pandas."""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
    
    def process_all(self, days: int | None = None) -> dict[str, list[Path]]:
        """Processa tudo (reais + virtuais)."""
        
        # 1. Discovery
        logger.info(f"🔍 Scanning {self.config.zips_dir}...")
        real_groups = discover_groups(self.config.zips_dir)
        
        logger.info(f"📦 Found {len(real_groups)} real group(s):")
        for slug, exports in real_groups.items():
            logger.info(f"  • {exports[0].group_name} ({slug}): {len(exports)} exports")
        
        # 2. Criar virtuais
        virtual_groups = create_virtual_groups(real_groups, self.config.merges)
        
        if virtual_groups:
            logger.info(f"🔀 Created {len(virtual_groups)} virtual group(s):")
            for slug, source in virtual_groups.items():
                logger.info(f"  • {source.name} ({slug}): merges {len(source.exports)} exports")
        
        # 3. Converter reais para GroupSource
        real_sources = {
            slug: GroupSource(
                slug=slug,
                name=exports[0].group_name,
                exports=exports,
                is_virtual=False,
            )
            for slug, exports in real_groups.items()
        }
        
        # 4. Combinar
        all_sources = {**real_sources, **virtual_groups}
        
        # 5. Filtrar
        sources_to_process = self._filter_sources(all_sources)
        
        # 6. Processar
        results = {}
        for slug, source in sources_to_process.items():
            logger.info(f"\n{'📺' if source.is_virtual else '📝'} Processing: {source.name}")
            
            if source.is_virtual:
                self._log_merge_stats(source)
            
            newsletters = self._process_source(source, days)
            results[slug] = newsletters
        
        return results
    
    def _log_merge_stats(self, source: GroupSource):
        """Log estatísticas de merge."""
        
        from .merger import merge_with_tags
        
        df = merge_with_tags(source.exports, source.merge_config)
        stats = get_merge_stats(df)
        
        logger.info(f"  Merging {len(stats)} groups:")
        for _, row in stats.iterrows():
            logger.info(f"    • {row['group_name']}: {row['message_count']} messages")
    
    def _filter_sources(self, all_sources: dict[str, GroupSource]) -> dict[str, GroupSource]:
        """Filtra sources a processar."""
        
        if not self.config.skip_real_if_in_virtual:
            return all_sources
        
        groups_in_merges = set()
        for merge_config in self.config.merges.values():
            groups_in_merges.update(merge_config.source_groups)
        
        filtered = {}
        for slug, source in all_sources.items():
            if source.is_virtual or slug not in groups_in_merges:
                filtered[slug] = source
            else:
                logger.info(f"  ⏭️  Skipping {source.name} (part of virtual group)")
        
        return filtered
    
    def _process_source(self, source: GroupSource, days: int | None) -> list[Path]:
        """Processa um source."""
        
        output_dir = self.config.newsletters_dir / source.slug
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse para descobrir datas disponíveis
        df = parse_multiple(source.exports)
        
        if df.empty:
            logger.warning(f"  No messages found")
            return []
        
        available_dates = sorted(df['date'].unique())
        target_dates = available_dates[-days:] if days else available_dates
        
        results = []
        
        for target_date in target_dates:
            logger.info(f"  Processing {target_date}...")
            
            # Extrai transcrito
            transcript = extract_transcript(source, target_date)
            
            if not transcript:
                logger.warning(f"    Empty transcript")
                continue
            
            # Stats
            stats = get_stats_for_date(source, target_date)
            logger.info(f"    {stats['message_count']} messages from {stats['participant_count']} participants")
            
            # Gera newsletter
            newsletter = self._generate_newsletter(source, transcript, target_date)
            
            # Salva
            output_path = output_dir / f"{target_date}.md"
            output_path.write_text(newsletter, encoding='utf-8')
            
            results.append(output_path)
            logger.info(f"    ✅ {output_path.relative_to(Path.cwd())}")
        
        return results
    
    def _generate_newsletter(
        self,
        source: GroupSource,
        transcript: str,
        target_date: date,
    ) -> str:
        """Gera newsletter."""
        
        from .pipeline import build_llm_input, call_gemini
        
        llm_input = build_llm_input(
            group_name=source.name,
            timezone=self.config.timezone,
            transcripts=[(target_date, transcript)],
            # ... enrichment, rag, etc
        )
        
        system_instruction = _build_system_instruction(
            has_group_tags=source.is_virtual
        )
        
        model = (
            source.merge_config.model_override 
            if source.is_virtual and source.merge_config.model_override
            else self.config.model
        )
        
        return call_gemini(llm_input, model, system_instruction)
    
    def list_groups(self) -> dict[str, dict]:
        """Lista grupos descobertos."""
        
        real_groups = discover_groups(self.config.zips_dir)
        virtual_groups = create_virtual_groups(real_groups, self.config.merges)
        
        all_info = {}
        
        # Reais
        for slug, exports in real_groups.items():
            dates = [e.export_date for e in exports]
            all_info[slug] = {
                'name': exports[0].group_name,
                'type': 'real',
                'export_count': len(exports),
                'date_range': (min(dates), max(dates)),
                'in_virtual': [
                    s for s, c in self.config.merges.items() 
                    if slug in c.source_groups
                ],
            }
        
        # Virtuais
        for slug, source in virtual_groups.items():
            dates = [e.export_date for e in source.exports]
            all_info[slug] = {
                'name': source.name,
                'type': 'virtual',
                'merges': source.merge_config.source_groups,
                'export_count': len(source.exports),
                'date_range': (min(dates), max(dates)),
            }
        
        return all_info


def _build_system_instruction(has_group_tags: bool = False) -> str:
    """System prompt único."""
    
    base = """
Tarefa: produzir uma newsletter diária a partir de conversas de grupo.

Objetivo:
- Newsletter organizada em FIOS (threads)
- Narrada no plural ("nós") como voz coletiva do grupo
- Autor entre parênteses após cada frase
- Links inseridos onde mencionados
- Explicitar contextos e subentendidos

🔒 PRIVACIDADE:
- Usar apenas identificadores anônimos (User-XXXX)
- Nunca reproduzir nomes, telefones, emails do conteúdo

Formatação:
1) Cabeçalho: "📩 {GRUPO} — Diário de {DATA}"
2) Fios com títulos descritivos
3) Conclusão reflexiva
    """
    
    if has_group_tags:
        base += """

⚠️ MENSAGENS TAGUEADAS:
- Este grupo agrega múltiplas fontes
- Tags indicam origem: [Grupo], 🌎, etc
- Mencione origem quando RELEVANTE
- Trate como conversa UNIFICADA
        """
    
    return base
```

### **FASE 7: CLI** (1 hora)

```python
# src/egregora/__main__.py

import argparse
from pathlib import Path

from .processor import UnifiedProcessor
from .config import PipelineConfig


def main():
    parser = argparse.ArgumentParser(
        description="Egregora: Multi-group WhatsApp newsletter generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  egregora                     # Process all groups
  egregora --days 7            # Last 7 days
  egregora --list              # List discovered groups
  egregora --config app.toml   # Use custom config
        """
    )
    
    parser.add_argument('--config', type=Path, help='Config TOML file')
    parser.add_argument('--zips-dir', type=Path, default=Path('data/whatsapp_zips'))
    parser.add_argument('--newsletters-dir', type=Path, default=Path('newsletters'))
    parser.add_argument('--days', type=int, help='Process N most recent days')
    parser.add_argument('--list', action='store_true', help='List groups and exit')
    parser.add_argument('--model', type=str, help='Override LLM model')
    
    args = parser.parse_args()
    
    # Load config
    if args.config and args.config.exists():
        config = PipelineConfig.from_toml(args.config)
        if args.model:
            config.model = args.model
    else:
        config = PipelineConfig.with_defaults(
            zips_dir=args.zips_dir,
            newsletters_dir=args.newsletters_dir,
            model=args.model,
        )
    
    processor = UnifiedProcessor(config)
    
    # List mode
    if args.list:
        groups = processor.list_groups()
        
        print("\n" + "="*60)
        print("📁 DISCOVERED GROUPS")
        print("="*60 + "\n")
        
        for slug, info in sorted(groups.items()):
            icon = "📺" if info['type'] == 'virtual' else "📝"
            print(f"{icon} {info['name']}")
            print(f"   Slug: {slug}")
            print(f"   Exports: {info['export_count']}")
            print(f"   Dates: {info['date_range'][0]} to {info['date_range'][1]}")
            
            if info['type'] == 'real' and info['in_virtual']:
                print(f"   Part of: {', '.join(info['in_virtual'])}")
            elif info['type'] == 'virtual':
                print(f"   Merges: {', '.join(info['merges'])}")
            
            print()
        
        print("="*60 + "\n")
        return
    
    # Process mode
    print("\n" + "="*60)
    print("🚀 PROCESSING")
    print("="*60)
    
    results = processor.process_all(days=args.days)
    
    # Summary
    print("\n" + "="*60)
    print("✅ COMPLETE")
    print("="*60 + "\n")
    
    total = sum(len(v) for v in results.values())
    print(f"Groups processed: {len(results)}")
    print(f"Newsletters generated: {total}\n")
    
    for slug, newsletters in sorted(results.items()):
        print(f"  {slug}: {len(newsletters)} newsletters")
    
    print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    main()
```

### **BONUS: Analytics** (1 hora)

```python
# src/egregora/analytics.py

import pandas as pd


def analyze_participation(df: pd.DataFrame) -> pd.DataFrame:
    """Top participantes."""
    
    return (
        df.groupby('author')
        .agg(
            message_count=('message', 'count'),
            first_seen=('timestamp', 'min'),
            last_seen=('timestamp', 'max'),
            avg_length=('message', lambda x: x.str.len().mean()),
        )
        .sort_values('message_count', ascending=False)
        .reset_index()
    )


def hourly_activity(df: pd.DataFrame) -> pd.Series:
    """Distribuição por hora."""
    return df.groupby(df['timestamp'].dt.hour).size()


def daily_activity(df: pd.DataFrame) -> pd.Series:
    """Mensagens por dia."""
    return df.groupby('date').size()


def detect_threads(df: pd.DataFrame, max_gap_minutes: int = 30) -> pd.DataFrame:
    """Identifica threads (gaps temporais)."""
    
    df = df.sort_values('timestamp').copy()
    df['gap_minutes'] = df['timestamp'].diff().dt.total_seconds() / 60
    df['new_thread'] = df['gap_minutes'] > max_gap_minutes
    df['thread_id'] = df['new_thread'].cumsum()
    
    return df


def thread_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Estatísticas por thread."""
    
    df_threads = detect_threads(df)
    
    return (
        df_threads.groupby('thread_id')
        .agg(
            start=('timestamp', 'min'),
            end=('timestamp', 'max'),
            messages=('message', 'count'),
            participants=('author', 'nunique'),
        )
        .assign(duration_min=lambda x: (x['end'] - x['start']).dt.total_seconds() / 60)
        .sort_values('messages', ascending=False)
        .reset_index()
    )
```

## 📊 Exemplos de Uso

### **Caso 1: Zero Config**

```bash
# Apenas roda
uv run egregora --days 7

# Output:
# 🔍 Scanning data/whatsapp_zips...
# 📦 Found 3 real group(s):
#   • RC LatAm (rc-latam): 10 exports
#   • Tech Team (tech-team): 5 exports
#   • Family (family): 3 exports
#
# 📝 Processing: RC LatAm
#   Processing 2025-10-01...
#     45 messages from 12 participants
#     ✅ newsletters/rc-latam/2025-10-01.md
# ...
# ✅ COMPLETE
# Groups processed: 3
# Newsletters generated: 18
```

### **Caso 2: Com Merges**

```bash
# egregora.toml
cat > egregora.toml << 'EOF'
[merges.rc-americas]
name = "RC Americas"
groups = ["rc-latam", "rc-brasil"]
tag_style = "emoji"
emojis = { rc-latam = "🌎", rc-brasil = "🇧🇷" }
EOF

uv run egregora --config egregora.toml --days 7

# Output:
# 🔍 Scanning...
# 📦 Found 3 real group(s):
#   • RC LatAm (rc-latam): 10 exports
#   • RC Brasil (rc-brasil): 8 exports
#   • Tech Team (tech-team): 5 exports
#
# 🔀 Created 1 virtual group(s):
#   • RC Americas (rc-americas): merges 18 exports
#
# ⏭️  Skipping RC LatAm (part of virtual group)
# ⏭️  Skipping RC Brasil (part of virtual group)
#
# 📝 Processing: Tech Team
# ...
# 📺 Processing: RC Americas
#   Merging 2 groups:
#     • RC LatAm: 45 messages
#     • RC Brasil: 38 messages
#   Processing 2025-10-01...
#     83 messages from 23 participants
#     ✅ newsletters/rc-americas/2025-10-01.md
```

### **Caso 3: Listar**

```bash
uv run egregora --list

# ============================================================
# 📁 DISCOVERED GROUPS
# ============================================================
#
# 📝 RC LatAm
#    Slug: rc-latam
#    Exports: 10
#    Dates: 2025-09-22 to 2025-10-01
#    Part of: rc-americas
#
# 📝 Tech Team
#    Slug: tech-team
#    Exports: 5
#    Dates: 2025-09-27 to 2025-10-01
#
# 📺 RC Americas
#    Slug: rc-americas
#    Exports: 18
#    Dates: 2025-09-22 to 2025-10-01
#    Merges: rc-latam, rc-brasil
# ============================================================
```

## ✅ Checklist

**Sprint 1 (3 dias):**
- [ ] models.py
- [ ] discovery.py
- [ ] parser.py
- [ ] Testes unitários

**Sprint 2 (2 dias):**
- [ ] merger.py
- [ ] transcript.py
- [ ] config.py
- [ ] egregora.toml.example

**Sprint 3 (2 dias):**
- [ ] processor.py
- [ ] Integração com pipeline existente
- [ ] Testes E2E

**Sprint 4 (1 dia):**
- [ ] __main__.py
- [ ] analytics.py (bonus)
- [ ] Documentação

## 📦 Dependencies

```toml
[project]
dependencies = [
    "pandas>=2.0.0",
    "google-genai",
]
```

## 🎯 Vantagens Pandas

1. **Código declarativo** - Menos bugs
2. **Performance** - Operações otimizadas
3. **Análises grátis** - groupby, stats, etc
4. **Debugging fácil** - df.head(), df.describe()
5. **Extensível** - Fácil adicionar features
6. **Interop** - CSV, Parquet, SQL
7. **Testável** - DataFrames fáceis de assert

---

**Pronto! 🚀** Plano completo usando pandas para manipulação de conversas.
