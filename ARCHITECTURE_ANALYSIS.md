# 📊 ANÁLISE DE ARQUITETURA - EGREGORA

**Data da Análise:** 2026-01-22
**Versão Analisada:** Current HEAD (commit e138d3b)
**Analista:** Claude (Sonnet 4.5)

---

## 1. RESUMO EXECUTIVO

O Egregora é um sistema sofisticado de transformação de conversas em narrativas conectadas, implementado com uma arquitetura em camadas bem definida:

**Stack Principal:**
- **Dados:** Ibis + DuckDB (OLAP local) + LanceDB (vector store)
- **IA:** Pydantic-AI + Google Gemini (2.5 Flash, com fallback)
- **Config:** Pydantic Settings + TOML
- **Output:** MkDocs Material (site estático)

**Filosofia:** "Invisible Intelligence, Visible Magic" - RAG, ranking e perfis de autores funcionam automaticamente sem configuração.

---

## 2. ✅ PONTOS FORTES DA ARQUITETURA

### A. Separação de Responsabilidades Clara

```
CLI → Orchestration → Agents → Database
      ↓               ↓
  Adapters      Transformations
```

- Cada camada tem responsabilidade bem definida
- Baixo acoplamento entre módulos
- Fácil navegação no código

### B. Extensibilidade por Design

- **Adapters Pattern:** Novos formatos de entrada (WhatsApp, Slack, etc.) via protocolo
- **Output Sinks:** Formatos de saída plugáveis (MkDocs, Notion, etc.)
- **Skills System:** Extensões customizadas via `.egregora/skills/`
- **Model Rotation:** Suporte a múltiplos LLMs via Pydantic-AI

### C. Resiliência Operacional

- **Journaling:** Idempotência - reprocessamento seguro de windows
- **Auto-split:** Janelas grandes divididas automaticamente em caso de `PromptTooLargeError`
- **Non-fatal failures:** Enrichment e media não bloqueiam pipeline
- **Task coalescing:** Otimiza updates redundantes de perfil

### D. Performance Consciente

- **Streaming:** Processa ZIPs grandes sem carregar tudo em memória
- **LRU Cache:** Embeddings com cache de 16 entradas
- **Lazy RAG:** Vector DB só inicializa quando necessário
- **Batch processing:** Banner generation em lote

### E. Type Safety & Testing

- MyPy strict mode na maioria dos módulos
- 216 arquivos de teste (unit, integration, e2e, benchmarks)
- Property-based testing com Hypothesis
- Snapshot testing com Syrupy

---

## 3. ⚠️ ÁREAS DE PREOCUPAÇÃO

### A. Complexidade do Orchestration Layer

**Problema:**
- `write.py` tem **1400+ linhas** - viola princípio de Single Responsibility
- `runner.py` com 578 linhas - dificulta manutenção
- Lógica de window splitting misturada com processamento

**Impacto:**
- Curva de aprendizado alta para novos contribuidores
- Dificulta testes unitários isolados
- Mudanças arriscadas (efeitos colaterais não óbvios)

**Evidência:**
```python
# write.py tem múltiplas responsabilidades:
- ETL setup
- Window iteration
- Agent execution
- Media processing
- Background task scheduling
- Error handling
```

**Localização:** `src/egregora/orchestration/pipelines/write.py:1-1400`

### B. Gestão de Estado Fragmentada

**Problema:**
- Estado distribuído entre: Journal, TaskStore, EloStore, ContentRepository
- Nenhuma visão unificada do "estado do pipeline"
- Difícil rastrear progresso de execução

**Impacto:**
- Debugging complexo em caso de falhas parciais
- Impossível "replay" de pipeline com estado consistente
- Checkpoints fragmentados

**Arquivos Afetados:**
- `src/egregora/orchestration/journal.py`
- `src/egregora/database/task_store.py`
- `src/egregora/database/elo_store.py`
- `src/egregora/database/repository.py`

### C. Configuração com Defaults Implícitos

**Problema:**
- Muitos defaults espalhados pelo código:
  - `DEFAULT_MODEL` em `config/settings.py`
  - `DEFAULT_EMBEDDING_MODEL` hardcoded
  - Magic numbers (0.8 / 5 para window splitting)
  - Rate limit = 2 req/s hardcoded

**Impacto:**
- Difícil entender comportamento real sem ler código
- Mudanças de defaults quebram sites existentes
- Testes dependem de valores mágicos

**Exemplo:**
```python
# src/egregora/orchestration/pipelines/write.py
if window_size > (max_tokens * 0.8 / 5):  # ??? Por que 0.8/5?
    split_proactively()
```

### D. Error Handling Inconsistente

**Problema:**
- Alguns erros são fatais, outros não (sem critério claro)
- Journal failures silenciadas mas importantes para idempotência
- Enrichment errors não propagados ao usuário

**Impacto:**
- Comportamento imprevisível em falhas
- Logs importantes perdidos
- Usuário não sabe quando features falharam

**Exemplo:**
```python
# Diferentes estratégias de erro sem padrão claro:
try:
    journal.persist()
except Exception:
    logger.warning("Journal failed")  # Silent fail

try:
    enrich_media()
except Exception:
    logger.error("Enrichment failed")  # Logged but continues

try:
    writer_agent.run()
except Exception:
    raise  # Fatal
```

### E. Testing Gaps

**Problema:**
- Coverage atual: **39%** (baixo para projeto crítico)
- Faltam testes de integração para RAG + Writer
- End-to-end tests com mocks - não validam LLM real
- Benchmarks não executam em CI

**Impacto:**
- Regressões podem passar despercebidas
- Mudanças arriscadas sem rede de segurança
- Performance pode degradar sem detecção

**Áreas Críticas Sem Cobertura:**
- `orchestration/runner.py` - Window processing loop
- `agents/writer.py` - RAG integration
- `rag/lancedb_backend.py` - Vector search

### F. Acoplamento ao Google Gemini

**Problema:**
- Todo pipeline depende de `GOOGLE_API_KEY`
- Pydantic-AI suporta outros providers, mas config não
- Fallback só entre modelos Gemini (não cross-provider)

**Impacto:**
- Vendor lock-in
- Falhas da Google API param todo pipeline
- Usuários sem Gemini não podem usar

**Código Afetado:**
```python
# src/egregora/config/settings.py
DEFAULT_MODEL = "google-gla:gemini-2.5-flash"  # Hardcoded Google

# src/egregora/llm/providers/model_cycler.py
# Só rotaciona entre modelos Gemini
```

### G. Documentação de Código Limitada

**Problema:**
- CLAUDE.md excelente, mas código tem poucos docstrings
- Funções complexas sem explicação (ex: window splitting heuristic)
- Falta de ADRs (Architecture Decision Records) para decisões críticas

**Impacto:**
- Onboarding difícil
- Decisões arquiteturais podem ser revertidas por desconhecimento
- AI agents (Jules) podem fazer mudanças incompatíveis

---

## 4. 🎯 RECOMENDAÇÕES PRIORIZADAS

### CRÍTICAS (Fazer Agora)

#### 1. Refatorar `orchestration/pipelines/write.py`

**Objetivo:** Dividir 1400 linhas em módulos coesos

**Plano:**
```python
# Proposta de estrutura:
orchestration/
├── pipelines/
│   ├── write.py (reduzir para ~200 linhas - entry point)
│   ├── etl/
│   │   ├── setup.py           # _prepare_pipeline_data()
│   │   └── conversation.py    # get_pending_conversations()
│   ├── execution/
│   │   ├── processor.py       # process_item()
│   │   └── window_handler.py  # window splitting logic
│   └── coordination/
│       ├── background_tasks.py
│       └── checkpointing.py
```

**Benefícios:**
- Testes unitários isolados
- Responsabilidades claras
- Fácil entender fluxo

**Arquivos a Criar:**
- `src/egregora/orchestration/pipelines/etl/setup.py`
- `src/egregora/orchestration/pipelines/etl/conversation.py`
- `src/egregora/orchestration/pipelines/execution/processor.py`
- `src/egregora/orchestration/pipelines/execution/window_handler.py`
- `src/egregora/orchestration/pipelines/coordination/background_tasks.py`
- `src/egregora/orchestration/pipelines/coordination/checkpointing.py`

**Esforço Estimado:** 3-5 dias

---

#### 2. Centralizar Configuração de Defaults

**Criar:** `src/egregora/config/defaults.py`

```python
# defaults.py
from dataclasses import dataclass

@dataclass(frozen=True)
class PipelineDefaults:
    """Pipeline processing defaults."""

    MAX_PROMPT_TOKENS: int = 400_000
    """Maximum tokens per prompt before auto-splitting."""

    PROACTIVE_SPLIT_THRESHOLD: float = 0.8
    """Threshold for proactive splitting (80% of max)."""

    PROACTIVE_SPLIT_DIVISOR: int = 5
    """Divisor for proactive split calculation."""

    STEP_SIZE: int = 100
    """Default window step size."""

    STEP_UNIT: str = "messages"
    """Default window step unit (messages, hours, bytes)."""

    OVERLAP_RATIO: float = 0.2
    """Overlap ratio between consecutive windows."""

@dataclass(frozen=True)
class ModelDefaults:
    """AI model defaults."""

    WRITER: str = "google-gla:gemini-2.5-flash"
    """Default model for Writer agent."""

    READER: str = "google-gla:gemini-2.5-flash"
    """Default model for Reader agent."""

    ENRICHER: str = "google-gla:gemini-2.5-flash"
    """Default model for Enrichment agent."""

    EMBEDDING: str = "models/gemini-embedding-001"
    """Default embedding model for RAG."""

@dataclass(frozen=True)
class RateLimitDefaults:
    """Rate limiting defaults."""

    REQUESTS_PER_SECOND: int = 2
    """Maximum requests per second to LLM APIs."""

    BURST_SIZE: int = 5
    """Maximum burst size for rate limiting."""
```

**Benefícios:**
- Descoberta fácil de configurações
- Documentação inline
- Testes não dependem de magic numbers
- Fácil override por ambiente

**Arquivos a Modificar:**
- `src/egregora/config/settings.py` - Importar de defaults
- `src/egregora/orchestration/pipelines/write.py` - Usar defaults
- `src/egregora/llm/rate_limit.py` - Usar defaults

**Esforço Estimado:** 1-2 dias

---

#### 3. Implementar Error Boundary Pattern

**Criar:** `src/egregora/orchestration/error_boundary.py`

```python
from enum import Enum
from typing import Protocol, Callable
from egregora.exceptions import EgregoraError

class FailureStrategy(Enum):
    """Strategy for handling different types of failures."""

    FATAL = "fatal"
    """Stop pipeline immediately and raise exception."""

    WARN = "warn"
    """Continue pipeline, log warning, notify user."""

    SILENT = "silent"
    """Continue pipeline, log at debug level."""

    RETRY = "retry"
    """Retry operation with exponential backoff."""

class ErrorBoundary(Protocol):
    """
    Define error handling policies for different operations.

    This centralizes error handling logic and makes behavior predictable.
    Each operation type has a clear failure strategy.
    """

    def handle_journal_error(self, e: Exception) -> None:
        """
        Handle journal persistence errors.

        Strategy: FATAL
        Reason: Breaks idempotency guarantees.
        """

    def handle_enrichment_error(self, e: Exception) -> None:
        """
        Handle media enrichment errors.

        Strategy: WARN
        Reason: Non-critical feature, user should know.
        """

    def handle_rag_error(self, e: Exception) -> None:
        """
        Handle RAG/vector search errors.

        Strategy: WARN + FALLBACK
        Reason: Degrades to no-context mode gracefully.
        """

    def handle_writer_error(self, e: Exception) -> None:
        """
        Handle Writer agent errors.

        Strategy: RETRY then FATAL
        Reason: Core feature, but may be transient API error.
        """

class DefaultErrorBoundary:
    """Default implementation of error boundary."""

    def __init__(self, logger, user_notifier):
        self.logger = logger
        self.notifier = user_notifier

    def handle_journal_error(self, e: Exception) -> None:
        self.logger.critical(f"Journal error: {e}")
        raise ConfigurationError("Cannot proceed without journal") from e

    def handle_enrichment_error(self, e: Exception) -> None:
        self.logger.warning(f"Enrichment failed: {e}")
        self.notifier.warn("Media enrichment unavailable for this batch")
        # Continue processing

    def handle_rag_error(self, e: Exception) -> None:
        self.logger.warning(f"RAG error: {e}")
        self.notifier.warn("Contextual memory unavailable, falling back to no-context mode")
        # Return empty context

    def handle_writer_error(self, e: Exception) -> None:
        # Retry logic handled by retry decorator
        self.logger.error(f"Writer error: {e}")
        raise  # Fatal
```

**Benefícios:**
- Comportamento previsível
- Fácil raciocinar sobre falhas
- Usuário sabe o que falhou
- Centralized error policy

**Arquivos a Modificar:**
- `src/egregora/orchestration/runner.py` - Usar error boundary
- `src/egregora/orchestration/pipelines/write.py` - Usar error boundary
- `src/egregora/agents/writer.py` - Usar error boundary

**Esforço Estimado:** 2-3 dias

---

### IMPORTANTES (Próximas Sprints)

#### 4. Aumentar Cobertura de Testes para 60%+

**Focos:**
- `orchestration/runner.py` - testes de window processing
- `agents/writer.py` - testes de RAG integration
- `rag/lancedb_backend.py` - testes de vector search
- `database/repository.py` - testes de persistence

**Estratégia:**
```bash
# Identificar módulos críticos sem cobertura:
uv run pytest --cov=egregora --cov-report=term-missing | grep "0%"

# Priorizar:
1. Lógica de negócio (agents, orchestration)
2. Persistência (database, repository)
3. Transformações (windowing, media)
```

**Testes a Criar:**

1. **`tests/unit/orchestration/test_runner_coverage.py`**
   - `test_window_processing_success()`
   - `test_window_auto_split_on_prompt_too_large()`
   - `test_journal_deduplication()`
   - `test_checkpoint_persistence()`

2. **`tests/integration/test_rag_writer_integration.py`**
   - `test_writer_uses_rag_context()`
   - `test_writer_fallback_no_rag()`
   - `test_rag_search_quality()`

3. **`tests/unit/database/test_repository_persistence.py`**
   - `test_content_repository_routes_document_types()`
   - `test_persistence_idempotency()`

**Esforço Estimado:** 5-7 dias

---

#### 5. Implementar Pipeline State Machine

**Objetivo:** Unificar gestão de estado do pipeline

**Criar:** `src/egregora/orchestration/state.py`

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

class PipelinePhase(Enum):
    """Pipeline execution phases."""

    INITIALIZING = "initializing"
    PARSING = "parsing"
    WINDOWING = "windowing"
    PROCESSING = "processing"
    PERSISTING = "persisting"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class PipelineState:
    """
    Unified pipeline state tracking.

    Provides single source of truth for pipeline progress,
    enabling recovery, monitoring, and debugging.
    """

    phase: PipelinePhase
    windows_total: int
    windows_processed: int
    posts_created: int
    profiles_created: int
    media_processed: int
    errors: list[Exception] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def checkpoint(self) -> dict:
        """Serialize state for recovery."""
        return {
            "phase": self.phase.value,
            "windows_total": self.windows_total,
            "windows_processed": self.windows_processed,
            "posts_created": self.posts_created,
            "profiles_created": self.profiles_created,
            "media_processed": self.media_processed,
            "errors": [str(e) for e in self.errors],
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def resume(cls, checkpoint: dict) -> "PipelineState":
        """Restore from checkpoint."""
        return cls(
            phase=PipelinePhase(checkpoint["phase"]),
            windows_total=checkpoint["windows_total"],
            windows_processed=checkpoint["windows_processed"],
            posts_created=checkpoint["posts_created"],
            profiles_created=checkpoint["profiles_created"],
            media_processed=checkpoint["media_processed"],
            errors=[Exception(e) for e in checkpoint["errors"]],
            started_at=datetime.fromisoformat(checkpoint["started_at"]),
            updated_at=datetime.fromisoformat(checkpoint["updated_at"]),
        )

    def progress_percentage(self) -> float:
        """Calculate progress as percentage."""
        if self.windows_total == 0:
            return 0.0
        return (self.windows_processed / self.windows_total) * 100

    def estimated_time_remaining(self) -> Optional[float]:
        """Estimate remaining time in seconds."""
        if self.windows_processed == 0:
            return None

        elapsed = (self.updated_at - self.started_at).total_seconds()
        avg_time_per_window = elapsed / self.windows_processed
        remaining_windows = self.windows_total - self.windows_processed

        return avg_time_per_window * remaining_windows
```

**Benefícios:**
- Visibilidade de progresso
- Recovery de falhas
- Debugging facilitado
- Estimativa de tempo
- Metrics para monitoring

**Integração:**
```python
# src/egregora/orchestration/runner.py
def run_pipeline(config):
    state = PipelineState(
        phase=PipelinePhase.INITIALIZING,
        windows_total=0,
        windows_processed=0,
        posts_created=0,
    )

    try:
        state.phase = PipelinePhase.PARSING
        messages = parse_input(config.input_path)

        state.phase = PipelinePhase.WINDOWING
        windows = create_windows(messages)
        state.windows_total = len(windows)

        state.phase = PipelinePhase.PROCESSING
        for window in windows:
            posts = process_window(window)
            state.posts_created += len(posts)
            state.windows_processed += 1
            state.updated_at = datetime.now()

            # Persist checkpoint
            save_checkpoint(state.checkpoint())

        state.phase = PipelinePhase.COMPLETED
    except Exception as e:
        state.phase = PipelinePhase.FAILED
        state.errors.append(e)
        raise
```

**Esforço Estimado:** 3-4 dias

---

#### 6. Adicionar Multi-Provider Support

**Objetivo:** Reduzir vendor lock-in

**Configuração:**
```toml
# .egregora.toml
[models.providers]
primary = "google-gla"
fallback = ["openai", "anthropic"]

[models.google-gla]
api_key_env = "GOOGLE_API_KEY"
default_model = "gemini-2.5-flash"

[models.openai]
api_key_env = "OPENAI_API_KEY"
default_model = "gpt-4o-mini"

[models.anthropic]
api_key_env = "ANTHROPIC_API_KEY"
default_model = "claude-sonnet-4-5"
```

**Implementação:**

**Criar:** `src/egregora/llm/provider_router.py`

```python
from typing import Protocol, Optional
from pydantic_ai import Agent
from egregora.config.settings import EgregoraConfig

class ProviderRouter:
    """
    Routes to next available provider on failures.

    Enables multi-provider fallback for resilience.
    """

    def __init__(self, config: EgregoraConfig):
        self.config = config
        self.current_provider_index = 0

    def get_next_model(self, current_error: Exception) -> Optional[str]:
        """
        Route to next provider in fallback chain.

        Args:
            current_error: Error from current provider

        Returns:
            Next model string or None if exhausted
        """
        from egregora.llm.exceptions import GoogleAPIError

        if isinstance(current_error, GoogleAPIError):
            # Move to OpenAI
            if "openai" in self.config.models.providers.fallback:
                return self.config.models.openai.default_model

        # Move to next in chain
        self.current_provider_index += 1

        if self.current_provider_index >= len(self.config.models.providers.fallback):
            return None  # Exhausted

        next_provider = self.config.models.providers.fallback[self.current_provider_index]
        return getattr(self.config.models, next_provider).default_model
```

**Modificar:** `src/egregora/agents/writer.py`

```python
# Add provider rotation logic
def create_writer_agent(config: EgregoraConfig) -> Agent:
    router = ProviderRouter(config)

    try:
        return Agent(model=config.models.writer, ...)
    except Exception as e:
        next_model = router.get_next_model(e)
        if next_model:
            return Agent(model=next_model, ...)
        raise
```

**Benefícios:**
- Reduz vendor lock-in
- Maior resiliência
- Flexibilidade de custos
- Fallback cross-provider

**Esforço Estimado:** 4-5 dias

---

### DESEJÁVEIS (Backlog)

#### 7. Performance Monitoring & Observability

**Adicionar:**
- Métricas: tempo por window, tokens consumidos, custo estimado
- Tracing: OpenTelemetry para rastrear fluxo
- Profiling: cProfile para identificar gargalos

**Implementação:**

**Criar:** `src/egregora/observability/metrics.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class WindowMetrics:
    """Metrics for window processing."""

    window_id: str
    start_time: datetime
    end_time: Optional[datetime]
    messages_count: int
    tokens_estimated: int
    tokens_actual: int
    api_calls: int
    api_cost_usd: float
    posts_created: int

    def duration_seconds(self) -> Optional[float]:
        if not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds()

class MetricsCollector:
    """Collect and export pipeline metrics."""

    def __init__(self):
        self.window_metrics: list[WindowMetrics] = []

    def record_window(self, metrics: WindowMetrics):
        self.window_metrics.append(metrics)

    def export_summary(self) -> dict:
        total_cost = sum(m.api_cost_usd for m in self.window_metrics)
        total_tokens = sum(m.tokens_actual for m in self.window_metrics)
        avg_duration = sum(m.duration_seconds() or 0 for m in self.window_metrics) / len(self.window_metrics)

        return {
            "total_windows": len(self.window_metrics),
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "avg_duration_seconds": avg_duration,
        }
```

**OpenTelemetry Integration:**

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("process_window")
def process_window(window: Window) -> list[str]:
    span = trace.get_current_span()
    span.set_attribute("window.size", len(window.messages))
    span.set_attribute("window.id", window.id)

    # Process...

    span.set_attribute("posts.created", len(posts))
    return posts
```

**Esforço Estimado:** 5-7 dias

---

#### 8. Implementar Dry-Run Mode

**Objetivo:** Validar pipeline sem executar LLM

**CLI:**
```bash
egregora write input.zip --dry-run
```

**Output:**
```
🔍 DRY RUN MODE - No LLM calls will be made

✓ Input file parsed successfully
  - Format: WhatsApp ZIP export
  - Messages: 12,453
  - Date range: 2023-01-15 to 2024-12-20
  - Authors: 5 (Alice, Bob, Charlie, Diana, Eve)

✓ Windowing configuration validated
  - Step size: 100 messages
  - Overlap: 20%
  - Estimated windows: 15

⚠ Window #7 will be auto-split
  - Reason: Estimated 450,000 tokens (exceeds 400,000 limit)
  - Sub-windows: 2

✓ Commands detected: 3
  - /egregora profile Alice
  - /avatar https://example.com/alice.jpg
  - /egregora tag important

✓ Media references: 42
  - Images: 35
  - Videos: 5
  - Audio: 2

💰 Cost Estimation:
  - RAG indexing: $2.50 (embeddings)
  - Writer agent: $15.00 (text generation)
  - Banner generation: $3.00 (image generation)
  - Total estimated: $20.50

⏱️ Time Estimation:
  - Based on rate limit: 2 req/s
  - Estimated duration: 8.5 minutes

✅ Dry run completed. Pipeline is ready to execute.
```

**Implementação:**

**Modificar:** `src/egregora/cli/write.py`

```python
@app.command()
def write(
    input_path: Path,
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without executing"),
):
    if dry_run:
        run_dry_run(input_path)
    else:
        run_pipeline(input_path)
```

**Criar:** `src/egregora/orchestration/dry_run.py`

```python
def run_dry_run(input_path: Path) -> DryRunReport:
    """Execute dry run validation."""

    # Parse input
    messages = parse_input(input_path)

    # Create windows
    windows = create_windows(messages)

    # Estimate tokens
    token_estimates = [estimate_tokens(w) for w in windows]

    # Detect auto-splits
    splits = [w for w in windows if needs_split(w)]

    # Extract commands
    commands = extract_commands(messages)

    # Count media
    media = extract_media_refs(messages)

    # Estimate cost
    cost = estimate_cost(windows, media)

    return DryRunReport(...)
```

**Esforço Estimado:** 3-4 dias

---

#### 9. Adicionar Architecture Decision Records (ADRs)

**Objetivo:** Documentar decisões arquiteturais críticas

**Criar:** `architecture/decisions/`

```
architecture/
├── decisions/
│   ├── 0001-use-ibis-instead-of-pandas.md
│   ├── 0002-duckdb-for-local-analytics.md
│   ├── 0003-pydantic-ai-for-structured-outputs.md
│   ├── 0004-lancedb-for-vector-search.md
│   ├── 0005-toml-over-yaml-config.md
│   └── template.md
└── README.md
```

**Template:** `architecture/decisions/template.md`

```markdown
# ADR-XXXX: [Title]

## Status

[Proposed | Accepted | Deprecated | Superseded]

## Context

[What is the issue that we're seeing that is motivating this decision or change?]

## Decision

[What is the change that we're proposing and/or doing?]

## Consequences

### Positive

- [Benefit 1]
- [Benefit 2]

### Negative

- [Drawback 1]
- [Drawback 2]

### Neutral

- [Trade-off 1]

## Alternatives Considered

### Alternative 1: [Name]

[Description and why rejected]

### Alternative 2: [Name]

[Description and why rejected]

## References

- [Link to discussion]
- [Link to implementation PR]
```

**Exemplo:** `architecture/decisions/0001-use-ibis-instead-of-pandas.md`

```markdown
# ADR-0001: Use Ibis Instead of Pandas

## Status

Accepted (2025-01-15)

## Context

Egregora needs to process chat message tables with 100k+ rows. Initial implementation used Pandas, but we faced:

1. **Backend lock-in**: Hard to migrate from DuckDB to PostgreSQL
2. **Memory issues**: Large DataFrames consume significant RAM
3. **Performance**: Pandas not optimized for analytics workloads

## Decision

Use Ibis as abstraction layer over DuckDB (and potentially other backends).

## Consequences

### Positive

- ✅ **Backend-agnostic**: Can switch from DuckDB to PostgreSQL/BigQuery without code changes
- ✅ **Lazy evaluation**: Queries optimized before execution
- ✅ **Better performance**: DuckDB optimizations for OLAP
- ✅ **Type safety**: Schema-aware operations

### Negative

- ❌ **Learning curve**: Ibis less common than Pandas
- ❌ **Smaller ecosystem**: Fewer integrations than Pandas
- ❌ **API differences**: Some operations require different syntax

### Neutral

- Requires explicit `.to_pandas()` when Pandas needed
- Need to maintain Ibis knowledge in team

## Alternatives Considered

### Alternative 1: Pure Pandas

**Pros:**
- Well-known API
- Large ecosystem
- Easy to hire for

**Cons:**
- Backend lock-in
- Memory inefficient
- Slower for large datasets

**Rejected because:** Backend lock-in and performance issues.

### Alternative 2: Pure SQL

**Pros:**
- Maximum control
- Optimal performance
- Portable

**Cons:**
- String concatenation for queries
- No type safety
- Hard to compose

**Rejected because:** Lack of type safety and composability.

## References

- Ibis documentation: https://ibis-project.org/
- DuckDB integration: https://ibis-project.org/backends/duckdb/
- Implementation PR: #123
```

**Esforço Estimado:** 2-3 days (initial ADRs)

---

#### 10. Documentar Padrões de Código

**Criar:** `architecture/patterns.md`

```markdown
# Padrões de Código Egregora

Este documento descreve os padrões de código estabelecidos no projeto Egregora.
Seguir esses padrões garante consistência e facilita manutenção.

---

## 1. Transformações Funcionais

**Sempre use funções puras para transformações de dados:**

```python
# ✅ BOM - Função pura
def filter_recent_messages(table: ibis.Table, days: int) -> ibis.Table:
    """Filter messages from last N days."""
    cutoff = datetime.now() - timedelta(days=days)
    return table.filter(ibis._['ts'] >= cutoff)

# ❌ RUIM - Efeitos colaterais
def filter_recent_messages(table: ibis.Table, days: int) -> ibis.Table:
    """Filter messages from last N days."""
    cutoff = datetime.now() - timedelta(days=days)
    filtered = table.filter(ibis._['ts'] >= cutoff)

    # Side effect: writes to database
    save_to_cache(filtered)  # ❌

    return filtered
```

**Regras:**
- Sem side effects (I/O, estado global, logging excessivo)
- Sem mutação de argumentos
- Resultado determinístico para mesmos inputs
- Composabilidade: `f(g(x))` deve funcionar

---

## 2. Error Handling

**Use exceções tipadas da hierarquia `EgregoraError`:**

```python
# ✅ BOM - Exceção tipada
from egregora.exceptions import ConfigurationError

def load_config(path: Path) -> EgregoraConfig:
    if not path.exists():
        raise ConfigurationError(f"Config file not found: {path}")

    try:
        return parse_toml(path)
    except TOMLDecodeError as e:
        raise ConfigurationError(f"Invalid TOML: {e}") from e

# ❌ RUIM - Exceção genérica
def load_config(path: Path) -> EgregoraConfig:
    if not path.exists():
        raise Exception("File not found")  # ❌ Não tipada
```

**Hierarquia:**
```
Exception
└── EgregoraError
    ├── ConfigurationError
    ├── AgentError
    ├── DatabaseError
    └── ...
```

**Regras:**
- Sempre derive de `EgregoraError`
- Use `from e` para chain de exceções
- Mensagens de erro devem ser actionable

---

## 3. Repository Pattern

**Abstraia acesso a dados com repositories:**

```python
# ✅ BOM - Repository com protocolo
from typing import Protocol

class MessageRepository(Protocol):
    def get_messages(self, filters: dict) -> ibis.Table: ...
    def count(self) -> int: ...

class DuckDBMessageRepository:
    def __init__(self, conn: DuckDBConnection):
        self.conn = conn

    def get_messages(self, filters: dict) -> ibis.Table:
        table = self.conn.table("messages")
        # Apply filters...
        return table

# Usage (dependency injection)
def process_pipeline(repo: MessageRepository):
    messages = repo.get_messages({"from_date": "2024-01-01"})
    # Process...

# ❌ RUIM - Acesso direto ao banco
def process_pipeline(conn):
    messages = conn.execute("SELECT * FROM messages WHERE ...")  # ❌
```

**Regras:**
- Use protocols para interfaces
- Repositories retornam Ibis Tables, não DataFrames
- Dependency injection para testabilidade

---

## 4. Adapter Pattern

**Use adapters para diferentes formatos de entrada/saída:**

```python
# ✅ BOM - Adapter com protocolo
from typing import Protocol
from pathlib import Path
import ibis

class InputAdapter(Protocol):
    def parse(self, input_path: Path) -> ibis.Table: ...
    def get_metadata(self, input_path: Path) -> dict: ...

class WhatsAppAdapter:
    def parse(self, input_path: Path) -> ibis.Table:
        # Parse WhatsApp ZIP
        return messages_table

    def get_metadata(self, input_path: Path) -> dict:
        return {"format": "whatsapp", "version": "2.0"}

# Registry pattern
ADAPTERS = {
    "whatsapp": WhatsAppAdapter,
    "telegram": TelegramAdapter,
}

# ❌ RUIM - Hard-coded format
def parse_input(path: Path) -> ibis.Table:
    if path.suffix == ".zip":
        return parse_whatsapp(path)  # ❌ Hard-coded
    elif path.suffix == ".json":
        return parse_telegram(path)  # ❌ Hard-coded
```

**Regras:**
- Protocols definem interface
- Registry para descoberta de adapters
- Retornar formato canônico (Ibis Table com schema padronizado)

---

## 5. Configuration Management

**Use Pydantic Settings para configuração:**

```python
# ✅ BOM - Pydantic Settings
from pydantic_settings import BaseSettings
from pydantic import Field

class PipelineConfig(BaseSettings):
    step_size: int = Field(default=100, ge=1, le=10000)
    step_unit: str = Field(default="messages", pattern="^(messages|hours|bytes)$")

    model_config = {
        "env_prefix": "EGREGORA_",
        "env_file": ".env",
    }

# Validation automática
config = PipelineConfig(step_size=50)  # ✅

# ❌ RUIM - Dict com validação manual
config = {
    "step_size": 50,
    "step_unit": "messages",
}

if config["step_size"] < 1:  # ❌ Validação manual
    raise ValueError("Invalid step_size")
```

**Regras:**
- Use Pydantic para validação
- Environment variables com prefix
- Defaults explícitos
- Validators para regras complexas

---

## 6. Testing Patterns

### Unit Tests

```python
# ✅ BOM - Unit test isolado
def test_filter_recent_messages():
    # Arrange
    table = create_test_table([
        {"ts": "2024-01-01", "content": "old"},
        {"ts": "2024-12-01", "content": "recent"},
    ])

    # Act
    result = filter_recent_messages(table, days=30)

    # Assert
    assert result.count().execute() == 1
    assert result.execute()["content"][0] == "recent"

# ❌ RUIM - Depende de estado externo
def test_filter_recent_messages():
    # ❌ Lê de arquivo externo
    table = load_from_file("test_data.csv")

    result = filter_recent_messages(table, days=30)

    # ❌ Assert vago
    assert result.count().execute() > 0
```

### Integration Tests

```python
# ✅ BOM - Integration test com fixture
@pytest.fixture
def temp_db():
    db_path = ":memory:"
    conn = ibis.duckdb.connect(db_path)
    yield conn
    conn.disconnect()

def test_repository_integration(temp_db):
    # Setup
    repo = DuckDBMessageRepository(temp_db)

    # Act
    messages = repo.get_messages({})

    # Assert
    assert isinstance(messages, ibis.Table)
```

---

## 7. Type Annotations

**Sempre use type hints:**

```python
# ✅ BOM - Type hints completos
def process_window(
    window: Window,
    config: EgregoraConfig,
    repo: ContentRepository,
) -> list[str]:
    """Process window and return post IDs."""
    posts: list[str] = []
    # ...
    return posts

# ❌ RUIM - Sem types
def process_window(window, config, repo):  # ❌
    posts = []
    return posts
```

**Regras:**
- Type hints em todos os parâmetros
- Type hints em retornos
- Use `typing.Protocol` para interfaces
- MyPy strict mode

---

## 8. Logging

**Use structured logging:**

```python
# ✅ BOM - Structured logging
import structlog

logger = structlog.get_logger()

def process_window(window: Window):
    logger.info(
        "processing_window",
        window_id=window.id,
        message_count=len(window.messages),
        start_time=window.start_time,
    )

# ❌ RUIM - String formatting
import logging

logger = logging.getLogger(__name__)

def process_window(window: Window):
    logger.info(f"Processing window {window.id} with {len(window.messages)} messages")  # ❌
```

**Regras:**
- Structured logging (key-value pairs)
- Levels apropriados (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Não logar informações sensíveis

---

## 9. Async/Await

**Use async para I/O-bound operations:**

```python
# ✅ BOM - Async para I/O
async def enrich_media_batch(media_refs: list[str]) -> list[Document]:
    tasks = [enrich_media(ref) for ref in media_refs]
    return await asyncio.gather(*tasks)

# ❌ RUIM - Sync para I/O-bound
def enrich_media_batch(media_refs: list[str]) -> list[Document]:
    results = []
    for ref in media_refs:
        results.append(enrich_media(ref))  # ❌ Blocking
    return results
```

**Regras:**
- Async para API calls, file I/O
- Sync para CPU-bound (transformações)
- Use `asyncio.gather` para paralelização

---

## 10. Docstrings

**Use Google-style docstrings:**

```python
# ✅ BOM - Google-style docstring
def create_windows(
    table: ibis.Table,
    step_size: int,
    step_unit: str,
) -> list[Window]:
    """
    Create windows from message table.

    Divides messages into overlapping windows for processing.

    Args:
        table: Message table (must have 'ts' column)
        step_size: Size of each window
        step_unit: Unit for step_size ('messages', 'hours', 'bytes')

    Returns:
        List of windows with overlapping boundaries

    Raises:
        ValueError: If step_unit is invalid

    Example:
        >>> table = create_test_table()
        >>> windows = create_windows(table, step_size=100, step_unit="messages")
        >>> len(windows)
        15
    """

# ❌ RUIM - Sem docstring ou docstring vaga
def create_windows(table, step_size, step_unit):
    """Create windows."""  # ❌ Muito vago
```

**Regras:**
- Google-style format
- Descrever Args, Returns, Raises
- Incluir Examples para funções complexas
- Obrigatório para APIs públicas

---

Seguir esses padrões garante código consistente, testável e manutenível.
```

**Esforço Estimado:** 2-3 days

---

## 5. 📋 PLANO DE AÇÃO SUGERIDO

### Sprint 1 (Semana 1-2): Fundações

**Objetivo:** Reduzir complexidade e centralizar configuração

- [ ] **Rec #1:** Refatorar `write.py` em módulos menores
  - Criar estrutura `etl/`, `execution/`, `coordination/`
  - Migrar funções para módulos apropriados
  - Atualizar imports
  - Executar testes

- [ ] **Rec #2:** Centralizar defaults em `config/defaults.py`
  - Criar `defaults.py` com dataclasses
  - Atualizar `settings.py` para importar defaults
  - Atualizar `write.py` e outros para usar defaults
  - Remover magic numbers

- [ ] **Rec #3:** Implementar Error Boundary pattern
  - Criar `orchestration/error_boundary.py`
  - Definir failure strategies
  - Integrar em `runner.py` e `write.py`
  - Adicionar testes

**Deliverables:**
- `write.py` reduzido para ~200 linhas
- `config/defaults.py` com todos defaults centralizados
- `orchestration/error_boundary.py` funcionando

---

### Sprint 2 (Semana 3-4): Qualidade

**Objetivo:** Aumentar cobertura de testes e visibilidade

- [ ] **Rec #4:** Aumentar coverage para 60%+ (focar em critical paths)
  - Identificar módulos sem cobertura
  - Criar testes para `runner.py`
  - Criar testes para integração RAG + Writer
  - Criar testes para `repository.py`

- [ ] **Rec #5:** Implementar Pipeline State Machine
  - Criar `orchestration/state.py`
  - Definir `PipelinePhase` enum
  - Integrar em `runner.py`
  - Adicionar checkpoint persistence

- [ ] Adicionar ADR-001 (Por que Ibis?)
  - Documentar decisão
  - Explicar trade-offs
  - Referenciar código

**Deliverables:**
- Coverage > 60%
- `orchestration/state.py` funcionando
- ADR-001 documentado

---

### Sprint 3 (Semana 5-6): Extensibilidade

**Objetivo:** Reduzir vendor lock-in e melhorar UX

- [ ] **Rec #6:** Multi-provider support (OpenAI fallback)
  - Atualizar `settings.py` para suportar múltiplos providers
  - Criar `llm/provider_router.py`
  - Integrar em `writer.py`
  - Adicionar testes

- [ ] **Rec #8:** Dry-run mode para estimativa de custo
  - Adicionar flag `--dry-run` ao CLI
  - Criar `orchestration/dry_run.py`
  - Implementar cost estimation
  - Adicionar formatação de output

- [ ] Documentar padrões de código
  - Criar `architecture/patterns.md`
  - Documentar 10 padrões principais
  - Adicionar examples

**Deliverables:**
- Suporte a OpenAI/Anthropic como fallback
- Comando `egregora write --dry-run` funcionando
- `architecture/patterns.md` completo

---

### Sprint 4 (Semana 7-8): Observabilidade

**Objetivo:** Monitoring e debugging

- [ ] **Rec #7:** Adicionar métricas básicas (tempo, tokens)
  - Criar `observability/metrics.py`
  - Integrar em `runner.py`
  - Exportar summary no final

- [ ] Implementar tracing básico
  - Adicionar OpenTelemetry
  - Instrumentar funções críticas
  - Configurar exporters

- [ ] Criar health checks
  - Comando `egregora health`
  - Verificar API keys
  - Verificar dependencies

**Deliverables:**
- Métricas de execução exportadas
- Tracing básico funcionando
- Comando `egregora health` implementado

---

## 6. 🎖️ CLASSIFICAÇÃO FINAL

### Arquitetura Geral: **8/10**

**Pontos Fortes:**
- ✅ Separação de camadas bem definida
- ✅ Extensibilidade por design (adapters, skills)
- ✅ Resiliência operacional (journaling, auto-split)
- ✅ Type safety com Pydantic + MyPy
- ✅ Performance consciente (streaming, cache)

**Pontos de Melhoria:**
- ⚠️ Complexidade em `orchestration/` (write.py 1400 linhas)
- ⚠️ Gestão de estado fragmentada
- ⚠️ Coverage de testes baixo (39%)
- ⚠️ Vendor lock-in (Google Gemini)
- ⚠️ Defaults implícitos (magic numbers)

---

### Manutenibilidade: **7/10**

**Positivo:**
- ✅ Código bem organizado em módulos lógicos
- ✅ Naming conventions consistentes
- ✅ Type annotations na maioria do código

**Negativo:**
- ⚠️ Falta documentação inline (docstrings)
- ⚠️ Alguns módulos muito grandes (`write.py`)
- ⚠️ Decisões arquiteturais não documentadas (falta ADRs)

---

### Testabilidade: **6/10**

**Positivo:**
- ✅ Boa estrutura de testes (unit/integration/e2e)
- ✅ Uso de property-based testing (Hypothesis)
- ✅ Snapshot testing para templates

**Negativo:**
- ⚠️ Coverage baixo (39%)
- ⚠️ Faltam testes de integração RAG
- ⚠️ E2E tests com mocks (não validam LLM real)

---

### Extensibilidade: **9/10**

**Positivo:**
- ✅ Excelente sistema de adapters
- ✅ Skills customizáveis
- ✅ Protocol-based design
- ✅ Output sinks plugáveis

**Negativo:**
- ⚠️ Vendor lock-in (Gemini apenas)

---

### Performance: **8/10**

**Positivo:**
- ✅ Streaming para grandes arquivos
- ✅ LRU cache para embeddings
- ✅ Lazy initialization (RAG)
- ✅ Batch processing (banners)

**Negativo:**
- ⚠️ Falta monitoring/profiling
- ⚠️ Sem benchmarks em CI

---

### Segurança: **7/10**

**Positivo:**
- ✅ Filesystem sandboxing
- ✅ Input validation com Pydantic
- ✅ SQL injection proteção (Ibis)

**Negativo:**
- ⚠️ API keys em variáveis de ambiente (não secrets manager)
- ⚠️ Falta rate limiting robusto

---

## 7. CONCLUSÃO

O Egregora demonstra **arquitetura sólida e bem pensada**, com clara separação de responsabilidades e foco em extensibilidade. As decisões técnicas (Ibis, Pydantic-AI, DuckDB) são justificadas e bem executadas.

**Principais oportunidades:**

1. **Refatoração de `write.py`** para reduzir complexidade ⭐ CRÍTICO
2. **Centralização de configuração** para facilitar descoberta ⭐ CRÍTICO
3. **Aumento de cobertura de testes** para garantir qualidade ⭐ IMPORTANTE
4. **Multi-provider support** para reduzir vendor lock-in ⭐ IMPORTANTE

**Com as recomendações implementadas**, a arquitetura evoluiria de **8/10 para 9.5/10**, mantendo a simplicidade enquanto ganha robustez e manutenibilidade.

---

## APÊNDICE A: Estrutura de Arquivos Detalhada

```
src/egregora/
├── orchestration/          # 578 LOC (runner.py)
│   ├── runner.py           # ⚠️ 578 linhas
│   ├── pipelines/
│   │   └── write.py        # ⚠️ 1400+ linhas - PRECISA REFATORAR
│   ├── context.py
│   ├── factory.py
│   ├── cache.py
│   ├── persistence.py
│   ├── journal.py
│   ├── materializer.py
│   └── worker_base.py
├── agents/                 # Pydantic-AI agents
│   ├── writer.py
│   ├── writer_*.py         # Writer utilities
│   ├── reader/
│   │   ├── agent.py
│   │   └── elo.py
│   ├── profile/
│   │   ├── generator.py
│   │   └── worker.py
│   ├── banner/
│   │   ├── agent.py
│   │   └── worker.py
│   └── capabilities.py
├── database/               # DuckDB + repositories
│   ├── duckdb_manager.py
│   ├── repository.py
│   ├── schemas.py
│   ├── views.py
│   ├── message_repository.py
│   ├── elo_store.py
│   ├── task_store.py
│   └── streaming/
│       └── stream.py
├── input_adapters/         # Source parsers
│   ├── base.py
│   ├── whatsapp/
│   │   └── adapter.py
│   ├── iperon_tjro.py
│   └── self_reflection.py
├── output_sinks/        # Format writers
│   ├── base.py
│   ├── mkdocs/
│   │   ├── adapter.py
│   │   └── paths.py
│   └── conventions.py
├── transformations/        # Pure functions
│   ├── windowing.py
│   └── media.py
├── rag/                    # Vector store
│   ├── backend.py
│   ├── lancedb_backend.py
│   ├── embedding_router.py
│   ├── embeddings.py
│   ├── chunking.py
│   └── ingestion.py
├── llm/                    # LLM integration
│   ├── api_keys.py
│   ├── model_fallback.py
│   ├── providers/
│   │   ├── model_cycler.py
│   │   └── model_key_rotator.py
│   ├── rate_limit.py
│   ├── retry.py
│   ├── token_utils.py
│   └── usage.py
├── config/                 # Configuration
│   ├── settings.py
│   └── defaults.py         # 🆕 A CRIAR
├── cli/                    # Command-line
│   ├── init.py
│   ├── write.py
│   ├── read.py
│   ├── show.py
│   └── health.py
├── data_primitives/        # Core abstractions
├── ops/                    # Operations
├── knowledge/              # Domain knowledge
├── resources/              # Prompts, SQL
├── rendering/              # Templates
├── security/               # Security utils
└── exceptions.py           # Exception hierarchy

tests/                      # 216 test files
├── unit/                   # ~100 files
├── integration/            # ~30 files
├── e2e/                    # ~15 files
├── features/               # ~20 files
├── security/               # ~10 files
├── benchmarks/             # ~10 files
├── evals/                  # ~10 files
├── skills/                 # ~5 files
└── fixtures/               # Test data

architecture/               # 🆕 A CRIAR
├── decisions/              # ADRs
│   ├── 0001-use-ibis-instead-of-pandas.md
│   ├── 0002-duckdb-for-local-analytics.md
│   └── template.md
└── patterns.md             # Code patterns
```

---

## APÊNDICE B: Métricas de Código

| Métrica | Valor | Status |
|---------|-------|--------|
| **Linhas de código (src/)** | ~15,000 | ✅ Médio |
| **Arquivos Python (src/)** | ~120 | ✅ Organizado |
| **Arquivos de teste** | 216 | ✅ Bom |
| **Coverage** | 39% | ⚠️ Baixo |
| **MyPy strict modules** | ~90% | ✅ Excelente |
| **Maior arquivo** | write.py (1400 LOC) | ⚠️ Refatorar |
| **Média LOC/arquivo** | ~125 | ✅ Razoável |
| **Complexidade ciclomática média** | ~8 | ✅ Aceitável |

---

## APÊNDICE C: Dependências Críticas

| Dependência | Versão | Propósito | Risco |
|-------------|--------|-----------|-------|
| `ibis-framework` | >=11.0 | Data abstraction | Baixo |
| `duckdb` | (via Ibis) | Local OLAP | Baixo |
| `lancedb` | >=0.25 | Vector store | Médio |
| `pydantic-ai` | >=1.25 | AI agents | Médio |
| `google-generativeai` | >=0.8.6 | Gemini API | **Alto** ⚠️ |
| `mkdocs-material` | >=9.7 | Site generation | Baixo |
| `typer` | >=0.20 | CLI | Baixo |
| `pytest` | (test) | Testing | Baixo |

**Risco Alto**: `google-generativeai` - Vendor lock-in, sem fallback cross-provider

---

**Documento gerado em:** 2026-01-22
**Próxima revisão:** Após Sprint 2 (estimado 2026-02-15)
