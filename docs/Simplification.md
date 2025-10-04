O usuário quer que eu crie o plano completo de simplificação em um artifact. Vou estruturar um documento detalhado em Markdown com todas as fases, itens de simplificação, riscos, validações e passos específicos.

Como as preferências do usuário dizem "Escreva documentos em artifacts, mas apenas depois de planejar e eu autorizar", e o usuário acabou de autorizar com "Sim", posso criar o artifact agora.

Vou criar um documento bem estruturado e detalhado com:
- Visão geral e objetivos
- Fase 1: Remoções (baixo risco)
- Fase 2: Consolidações (médio risco)
- Fase 3: Simplificações arquiteturais (maior risco)
- Cronograma sugerido
- Métricas de sucesso

Vou criar o plano completo de simplificação do Egregora:

```markdown
# 🎯 Plano de Simplificação do Egregora

**Versão:** 1.0  
**Data:** 2025-10-03  
**Objetivo:** Reduzir complexidade do código em ~40% mantendo todas as funcionalidades essenciais

---

## 📊 Visão Geral

### Métricas Atuais
- **Arquivos de configuração:** 8+ classes distintas
- **Sistema de backlog:** ~1000 linhas (complexo)
- **Documentação especulativa:** ~500 linhas não implementadas
- **Opções de configuração:** 50+ parâmetros
- **Sistemas de cache:** 3 implementações diferentes

### Objetivos de Simplificação
- ✂️ Remover 30-40% do código não essencial
- 🔄 Consolidar configurações em arquivo único
- 📝 Eliminar documentação de features não implementadas
- 🧹 Unificar sistemas duplicados (cache, logging, async)
- 🎯 Manter 100% da funcionalidade atual

### Princípios
1. **Simplicidade primeiro:** Remover antes de refatorar
2. **Segurança:** Validar cada mudança com testes
3. **Incremental:** Pequenos passos verificáveis
4. **Reversível:** Git branches para cada fase

---

## 🗺️ Fases do Plano

### Fase 1: Remoções (Baixo Risco) - 1 semana
Remover código morto e documentação especulativa sem afetar funcionalidade.

### Fase 2: Consolidações (Médio Risco) - 2 semanas  
Unificar sistemas duplicados mantendo comportamento idêntico.

### Fase 3: Simplificações Arquiteturais (Alto Risco) - 2 semanas
Simplificar arquitetura de componentes complexos.

---

## 🔴 FASE 1: REMOÇÕES (BAIXO RISCO)

### 1.1 Remover Sistema de Backlog Complexo 🔴

**O que remover:**
```
src/egregora/config.py:
  - BacklogProcessingConfig
  - BacklogAPIConfig
  - BacklogEnrichmentConfig
  - BacklogRAGConfig
  - BacklogLoggingConfig
  - BacklogCheckpointConfig
  - BacklogConfig (~200 linhas)
```

**Por que:**
- Sistema de 1000+ linhas para fazer o que 70 linhas fazem
- Checkpoint/resume nunca usado em produção
- Complexidade desnecessária para processar ZIPs

**Passos:**
1. ✅ Verificar que `scripts/process_backlog.py` (70 linhas) funciona
2. 🗑️ Remover todas as classes `Backlog*` de `config.py`
3. 🗑️ Remover função `load_backlog_config()`
4. 📝 Atualizar `docs/backlog_processing.md` (já documenta solução simples)
5. 🗑️ Remover arquivo `scripts/backlog_config.yaml` se existir

**Validação:**
```bash
# Testar script simples
python scripts/process_backlog.py data/zips newsletters/

# Verificar testes passam
pytest tests/test_core_pipeline.py
```

**Riscos:** ⚠️ Baixo - Script simples já é a solução recomendada
**Esforço:** 🕐 2 horas

---

### 1.2 Remover Documentação Especulativa 🔴

**O que remover:**
```
docs/ia-parquet.md              # ~500 linhas, feature não implementada
src/egregora/ia-parquet.md      # Duplicado
docs/llamaindex_migration_plan.md  # Migração já completa
MIGRATION_GUIDE.md              # Desatualizado
TESTING_PLAN.md                 # Coberto por testes reais
```

**Por que:**
- Confunde novos desenvolvedores
- Documentação de features que não existem
- Promessas não cumpridas no código

**Passos:**
1. 🗑️ `rm docs/ia-parquet.md src/egregora/ia-parquet.md`
2. 🗑️ `rm docs/llamaindex_migration_plan.md`
3. 🗑️ `rm MIGRATION_GUIDE.md TESTING_PLAN.md`
4. 📝 Adicionar seção "Future Ideas" no README.md para ideas de Parquet/Archive se necessário
5. 📝 Consolidar informações de teste relevantes no README.md

**Validação:**
- Revisar README.md para garantir info essencial está presente
- Verificar links na documentação não quebram

**Riscos:** ⚠️ Nenhum - Documentação especulativa
**Esforço:** 🕐 1 hora

---

### 1.3 Remover Código Morto do RAG 🔴

**O que remover:**
```python
# Em RAGConfig:
use_semantic_chunking: bool = False      # Não implementado
enable_hybrid_search: bool = False       # Não implementado

# Código relacionado a features futuras não usadas
```

**Por que:**
- Flags para features não implementadas
- Promessas no código que confundem

**Passos:**
1. 🔍 Buscar por `use_semantic_chunking` e `enable_hybrid_search`
2. 🗑️ Remover parâmetros de `RAGConfig`
3. 🗑️ Remover comentários sobre "future iterations"
4. 📝 Atualizar docstrings

**Validação:**
```bash
# Buscar referências
rg "use_semantic_chunking|enable_hybrid_search"

# Testes devem passar
pytest tests/test_rag*.py
```

**Riscos:** ⚠️ Nenhum - Features não implementadas
**Esforço:** 🕐 30 minutos

---

### 1.4 Remover Formatos de Anonimização Não Usados 🟡

**O que simplificar:**
```python
# Atual: 3 formatos
output_format: FormatType = "human" | "short" | "full"

# Proposta: 1 formato
output_format: str = "human"  # Removido
```

**Por que:**
- Apenas "human" é usado na prática
- Complexidade desnecessária

**Passos:**
1. 🔍 Verificar uso de formatos "short" e "full" no código
2. Se não usados, remover `FormatType` enum
3. Remover parâmetro `output_format` de `AnonymizationConfig`
4. Simplificar `Anonymizer` para sempre usar formato "human"
5. Atualizar testes

**Validação:**
```bash
# Verificar uso
rg "output_format|FormatType"

# Testes
pytest tests/test_anonymizer.py -v
```

**Riscos:** ⚠️ Baixo - Se outros formatos nunca usados
**Esforço:** 🕐 1 hora

---

### 1.5 Consolidar Workflows do GitHub 🟡

**O que fazer:**
```
.github/workflows/
  claude-code-review.yml  # Review automático de PRs
  claude.yml             # Claude on-demand com @mention
```

**Por que:**
- Duplicação de configuração
- Um workflow pode fazer ambos

**Passos:**
1. 📝 Mesclar funcionalidade em `claude.yml`
2. Adicionar trigger de PR review
3. 🗑️ Remover `claude-code-review.yml`
4. 📝 Documentar workflow único no README

**Validação:**
- Testar com PR de teste
- Verificar @claude mentions funcionam

**Riscos:** ⚠️ Médio - Pode afetar CI/CD
**Esforço:** 🕐 1 hora

---

## 🟡 FASE 2: CONSOLIDAÇÕES (MÉDIO RISCO)

### 2.1 Consolidar Arquivos de Configuração 🔴

**O que consolidar:**
```python
# Atual: 8 classes separadas
PipelineConfig
EnrichmentConfig
CacheConfig
AnonymizationConfig
PrivacyConfig
RAGConfig
MCPServerConfig

# Proposta: 1 arquivo TOML + 1 classe
```

**Estrutura proposta:**
```toml
# egregora.toml

[pipeline]
group_name = "RC LatAm"
model = "gemini-flash-lite-latest"
timezone = "America/Porto_Velho"

[directories]
zips_dir = "data/whatsapp_zips"
newsletters_dir = "newsletters"
media_dir = "media"
cache_dir = "cache"

[anonymization]
enabled = true

[privacy]
double_check_newsletter = false

[enrichment]
enabled = true
model = "gemini-2.0-flash-exp"
max_links = 50
max_concurrent = 5
timeout_seconds = 120.0

[cache]
enabled = true
auto_cleanup_days = 90
max_disk_mb = 100

[rag]
enabled = false
top_k = 5
min_similarity = 0.65
exclude_recent_days = 7
embedding_model = "models/gemini-embedding-001"
```

**Passos:**
1. 📝 Criar `egregora.toml.example` com valores padrão
2. 📝 Criar classe única `EgregoraConfig` que lê o TOML
3. 🔄 Refatorar `PipelineConfig.with_defaults()` para ler do TOML
4. 🔄 Atualizar todos os pontos de uso
5. 🗑️ Remover classes de config antigas gradualmente
6. 📝 Atualizar documentação

**Validação:**
```bash
# Testes com config padrão
pytest tests/

# Teste com config customizado
cp egregora.toml.example egregora.toml
# editar valores
uv run egregora --config egregora.toml
```

**Riscos:** ⚠️ Médio - Afeta todo o pipeline
**Mitigação:** 
- Manter compatibilidade com valores padrão
- Fazer em branch separado
- Testes extensivos

**Esforço:** 🕐 4 horas

---

### 2.2 Unificar Sistema de Cache 🔴

**Problema atual:**
```python
# 3 sistemas diferentes:
1. CacheManager (enrichment) - cache/index.json
2. EmbeddingCache (RAG) - cache/rag/embeddings.pkl
3. Vector store cache - cache/rag/vector_store/
```

**Proposta:**
```python
# 1 sistema unificado
class UnifiedCache:
    """Cache único para enrichment, embeddings e índices."""
    
    def __init__(self, base_dir: Path):
        self.enrichment = EnrichmentCache(base_dir / "enrichment")
        self.embeddings = EmbeddingCache(base_dir / "embeddings")
        self.vectors = VectorCache(base_dir / "vectors")
```

**Passos:**
1. 📝 Criar `src/egregora/cache.py` com interface unificada
2. 🔄 Migrar `CacheManager` para usar novo sistema
3. 🔄 Migrar embedding cache para usar nova estrutura
4. 📝 Atualizar `cache/README.md`
5. 🧪 Testes de migração de cache antigo → novo

**Validação:**
```bash
# Migração de cache existente
python scripts/migrate_cache.py

# Testes
pytest tests/test_cache*.py
```

**Riscos:** ⚠️ Médio - Perda de cache existente
**Mitigação:**
- Script de migração automática
- Backup de cache antes de migrar

**Esforço:** 🕐 3 horas

---

### 2.3 Unificar Helper de Async/Event Loop 🟡

**Problema:**
Código duplicado em 3+ lugares:
```python
def _run_async(coro: Awaitable[T]) -> T:
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
```

**Solução:**
```python
# src/egregora/utils.py (novo arquivo)
"""Utility functions shared across the project."""

def run_async(coro: Awaitable[T]) -> T:
    """Run async coroutine safely, handling existing event loops."""
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "event loop" not in str(exc).lower():
            raise
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
```

**Passos:**
1. 📝 Criar `src/egregora/utils.py`
2. 🔄 Substituir todas as ocorrências por `from egregora.utils import run_async`
3. 🧪 Testes unitários para `run_async()`

**Validação:**
```bash
# Buscar duplicação
rg "asyncio\.run|new_event_loop" -A 5

# Testes
pytest tests/test_utils.py
```

**Riscos:** ⚠️ Baixo - Lógica simples
**Esforço:** 🕐 30 minutos

---

### 2.4 Consolidar Sistema de Logging 🟡

**Problema:**
```python
# Função custom _emit()
def _emit(msg, logger=None, batch_mode=False, level="info"):
    ...

# Logs diretos com print()
print("[MCP Server] Inicializando RAG...")

# Logger padrão em alguns lugares
logger.info("...")
```

**Solução:**
```python
# src/egregora/logging_config.py
"""Centralized logging configuration."""

import logging
from pathlib import Path

def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Path | None = None,
    batch_mode: bool = False,
) -> logging.Logger:
    """Configure consistent logger for egregora modules."""
    ...
```

**Passos:**
1. 📝 Criar `logging_config.py` com configuração padrão
2. 🔄 Substituir `_emit()` por logger padrão
3. 🔄 Substituir `print()` por logger
4. 📝 Adicionar exemplo de uso no README

**Validação:**
```bash
# Verificar uso consistente
rg "print\(|_emit\(" src/

# Testes
pytest tests/ -v --log-cli-level=DEBUG
```

**Riscos:** ⚠️ Baixo - Logging é ortogonal
**Esforço:** 🕐 2 horas

---

### 2.5 Simplificar Imports Opcionais 🟡

**Problema:**
```python
try:
    import genai
except ModuleNotFoundError:
    genai = None

try:
    from mcp import Server
except:
    Server = None
    
# ... muitos blocos similares
```

**Solução:**
```python
# src/egregora/dependencies.py
"""Optional dependency management."""

class OptionalDependency:
    """Lazy import with clear error messages."""
    
    def __init__(self, module_name: str, package_name: str | None = None):
        self.module_name = module_name
        self.package_name = package_name or module_name
        self._module = None
    
    def __call__(self):
        if self._module is None:
            try:
                self._module = __import__(self.module_name)
            except ModuleNotFoundError:
                raise RuntimeError(
                    f"'{self.package_name}' não instalado. "
                    f"Instale com: pip install {self.package_name}"
                )
        return self._module

# Uso:
genai = OptionalDependency("google.generativeai", "google-genai")
mcp = OptionalDependency("mcp")
```

**Passos:**
1. 📝 Criar `src/egregora/dependencies.py`
2. 🔄 Substituir blocos try/except por `OptionalDependency`
3. 📝 Documentar dependências opcionais no README

**Validação:**
```bash
# Testes sem dependências opcionais
pip uninstall mcp -y
pytest tests/test_pipeline.py  # Deve passar

# Testes com dependências
pip install mcp
pytest tests/test_rag*.py
```

**Riscos:** ⚠️ Baixo - Melhor UX em erros
**Esforço:** 🕐 1.5 horas

---

## 🟢 FASE 3: SIMPLIFICAÇÕES ARQUITETURAIS

### 3.1 Simplificar Sistema de Perfis 🟡

**Problema:**
```python
@dataclass
class ParticipantProfile:
    # 15+ campos complexos
    worldview_summary: str
    core_interests: dict
    thinking_style: str
    values_and_priorities: list
    expertise_areas: dict
    contribution_style: str
    argument_patterns: list
    questioning_approach: str
    intellectual_influences: list
    aligns_with: list
    debates_with: list
    recent_shifts: list
    growing_interests: list
    interaction_patterns: dict
    analysis_version: int
```

**Proposta simplificada:**
```python
@dataclass
class ParticipantProfile:
    """Perfil simplificado focado no essencial."""
    
    member_id: str
    summary: str  # Resumo em texto livre
    interests: list[str]  # 5-10 interesses principais
    interaction_style: str  # Como a pessoa interage
    last_updated: datetime
    
    def to_markdown(self) -> str:
        """Formato legível para humanos."""
        return f"""
# {self.member_id}

{self.summary}

**Interesses:** {', '.join(self.interests)}
**Estilo:** {self.interaction_style}
"""
```

**Por que:**
- 15 campos é over-engineering
- Difícil de popular e manter
- Maioria dos campos fica vazia
- LLM consegue mesma qualidade com prompt simples

**Passos:**
1. 📝 Criar `ParticipantProfileV2` simplificado
2. 🔄 Migrar prompt de geração para novo formato
3. 📝 Script de migração de perfis antigos → novos
4. 🧪 Comparar qualidade de newsletters com ambos
5. Se qualidade OK, substituir completamente

**Validação:**
```bash
# Gerar newsletter com perfil antigo
uv run egregora --days 1

# Gerar com perfil novo
uv run egregora --days 1 --use-simple-profiles

# Comparar qualidade
diff newsletters/old/ newsletters/new/
```

**Riscos:** ⚠️ Alto - Pode afetar qualidade
**Mitigação:**
- A/B test em paralelo
- Manter ambos inicialmente
- Validação humana de qualidade

**Esforço:** 🕐 4 horas

---

### 3.2 Simplificar RAG: Escolher Vector Store Padrão 🟡

**Problema:**
```python
# Duas opções com código condicional complexo
vector_store_type: str = "simple" | "chroma"

if store_type == "chroma":
    # 15 linhas de setup
elif store_type == "simple":
    # Código diferente
```

**Proposta:**
- Escolher ChromaDB como padrão único
- Remover SimpleVectorStore
- Ou vice-versa se Simple é suficiente

**Passos:**
1. 🔍 Avaliar qual é melhor para uso real:
   - ChromaDB: persistência, melhor para produção
   - Simple: mais fácil, sem deps extras
2. 🗑️ Remover código da opção não escolhida
3. 📝 Simplificar `_init_vector_store()`
4. 📝 Atualizar documentação

**Decisão recomendada:** 
- **ChromaDB** para produção
- Remover SimpleVectorStore

**Validação:**
```bash
# Migrar índice existente
python scripts/migrate_vector_store.py

# Testes
pytest tests/test_rag*.py
```

**Riscos:** ⚠️ Médio - Mudança de dependência
**Esforço:** 🕐 2 horas

---

### 3.3 RAG: MCP vs Local - Escolher Um 🟡

**Problema:**
```python
if config.rag.use_mcp:
    try:
        context = _collect_rag_context_via_mcp(...)
    except:
        # Fallback para local
        context = _collect_rag_context_local(...)
else:
    context = _collect_rag_context_local(...)
```

**Proposta:**
- Usar APENAS local integration (mais simples)
- Ou usar APENAS MCP (mais desacoplado)
- Remover fallback complexo

**Decisão recomendada:**
- **Local** para simplicidade
- MCP é overhead desnecessário para uso em biblioteca

**Passos:**
1. 🗑️ Remover `_collect_rag_context_via_mcp()`
2. 🗑️ Remover flag `use_mcp` de config
3. 🗑️ Simplificar `_collect_rag_context()` para sempre usar local
4. 📝 MCP server continua existindo para Claude Desktop

**Validação:**
```bash
# Pipeline deve funcionar sem MCP
uv run egregora --days 1

# MCP server standalone ainda funciona
uv run python -m egregora.mcp_server.server
```

**Riscos:** ⚠️ Baixo - Funcionalidade preservada
**Esforço:** 🕐 1 hora

---

### 3.4 Remover Double-Check de Privacidade 🟢

**Análise:**
```python
# Camada 1: Anonimização ✅ (necessária)
# Camada 2: Instruções ao LLM ✅ (necessária)
# Camada 3: Revisão dupla ❓ (provavelmente desnecessária)

if config.privacy.double_check_newsletter:
    revised = _run_privacy_review(...)
```

**Proposta:**
- Remover opção de double-check
- Confiar em Anonimização + Instruções
- Simplificar fluxo

**Passos:**
1. 🔍 Verificar se double-check está sendo usado
2. Se não, remover completamente
3. 🗑️ Remover `PrivacyConfig.double_check_newsletter`
4. 🗑️ Remover `_run_privacy_review()`
5. 📝 Atualizar docs de privacidade

**Validação:**
```bash
# Verificar uso
rg "double_check_newsletter|_run_privacy_review"

# Newsletters mantêm qualidade
uv run egregora --days 7
# Revisar manualmente privacidade
```

**Riscos:** ⚠️ Médio - Privacidade é sensível
**Mitigação:**
- Validar que Camadas 1+2 são suficientes
- Documentar claramente processo de privacidade

**Esforço:** 🕐 1 hora

---

### 3.5 Simplificar EnrichmentConfig 🟢

**Problema:**
```python
@dataclass
class EnrichmentConfig:
    enabled: bool = True
    enrichment_model: str = "gemini-2.0-flash-exp"
    max_links: int = 50
    context_window: int = 3
    relevance_threshold: int = 2
    max_concurrent_analyses: int = 5
    max_total_enrichment_time: float = 120.0
```

**Proposta:**
```python
@dataclass
class EnrichmentConfig:
    enabled: bool = True
    max_links: int = 50
    timeout_seconds: float = 120.0
    # Remover: context_window, relevance_threshold, max_concurrent
    # Usar valores hard-coded sensatos
```

**Por que:**
- Usuários raramente mudam esses valores
- Aumenta complexidade sem benefício
- Valores padrão são bons

**Passos:**
1. 🔍 Verificar se parâmetros são alterados em algum lugar
2. 🗑️ Remover parâmetros não usados
3. 🔒 Hard-code valores sensatos no código
4. 📝 Documentar valores escolhidos

**Validação:**
```bash
# Buscar customizações
rg "context_window|relevance_threshold|max_concurrent"

# Testes
pytest tests/test_enrichment*.py
```

**Riscos:** ⚠️ Baixo - Valores raramente mudados
**Esforço:** 🕐 30 minutos

---

## 📅 Cronograma Sugerido

### Semana 1: Fase 1 - Remoções
- **Dia 1-2:** Items 1.1, 1.2 (Backlog + Docs)
- **Dia 3:** Items 1.3, 1.4 (RAG + Anonimização)
- **Dia 4:** Item 1.5 (Workflows)
- **Dia 5:** Validação e testes

### Semana 2-3: Fase 2 - Consolidações
- **Dia 1-2:** Item 2.1 (Consolidar configs) 🔴
- **Dia 3:** Item 2.2 (Unificar cache) 🔴
- **Dia 4:** Items 2.3, 2.4 (Async + Logging)
- **Dia 5:** Item 2.5 (Imports opcionais)

### Semana 4-5: Fase 3 - Arquitetura
- **Dia 1-2:** Item 3.1 (Perfis simplificados)
- **Dia 3:** Items 3.2, 3.3 (RAG)
- **Dia 4:** Items 3.4, 3.5 (Privacy + Enrichment)
- **Dia 5:** Validação final e documentação

**Total estimado:** ~40 horas de trabalho

---

## ✅ Checklist de Validação

Para cada fase, garantir:

- [ ] Todos os testes passam (`pytest tests/ -v`)
- [ ] Pipeline principal funciona (`uv run egregora --days 1`)
- [ ] Servidor MCP inicia (`uv run python -m egregora.mcp_server.server`)
- [ ] Backlog processa
