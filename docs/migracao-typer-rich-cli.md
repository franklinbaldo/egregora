# Migração CLI: argparse → Typer + Rich

**Data:** 4 de outubro de 2025  
**Objetivo:** Modernizar o CLI do Egregora usando Typer (comandos) e Rich (output)  
**Esforço estimado:** 3-5 dias  
**Impacto:** ⭐⭐⭐⭐⭐ Transformacional para UX

---

## 🎯 Por que Typer + Rich?

### Problemas com argparse atual
```python
# Atual: 150+ linhas verbosas
parser = argparse.ArgumentParser(...)
parser.add_argument("--zips-dir", type=Path, default=None, help="...")
parser.add_argument("--newsletters-dir", type=Path, default=None, help="...")
parser.add_argument("--model", type=str, default=None, help="...")
parser.add_argument("--timezone", type=str, default=None, help="...")
parser.add_argument("--days", type=int, default=2, help="...")
parser.add_argument("--enable-enrichment", action="store_true", help="...")
parser.add_argument("--disable-enrichment", action="store_true", help="...")
# ... +15 argumentos
```

### Benefícios da nova stack

**Typer:**
- ✅ Type hints nativos → menos boilerplate
- ✅ Validação automática de tipos
- ✅ Help text automático e bonito
- ✅ Subcomandos elegantes
- ✅ Auto-completion para shell

**Rich:**
- ✅ Output colorido e estruturado
- ✅ Tabelas formatadas
- ✅ Progress bars automáticos
- ✅ Panels e syntax highlighting
- ✅ Melhor feedback visual

---

## 📦 Dependências

```toml
# pyproject.toml
[project]
dependencies = [
    "google-genai>=0.3.0",
    "typer>=0.12.0",
    "rich>=13.7.0",
    # ... resto
]
```

```bash
# Instalação
uv add typer rich
```

---

## 🔄 Refatoração Completa

### Antes: argparse (150 linhas)

```python
# src/egregora/__main__.py (atual)

import argparse
import sys
from pathlib import Path

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera newsletters diárias a partir dos exports do WhatsApp."
    )
    
    parser.add_argument("--zips-dir", type=Path, default=None, help="...")
    parser.add_argument("--newsletters-dir", type=Path, default=None, help="...")
    parser.add_argument("--model", type=str, default=None, help="...")
    parser.add_argument("--timezone", type=str, default=None, help="...")
    parser.add_argument("--days", type=int, default=2, help="...")
    parser.add_argument("--enable-enrichment", action="store_true", help="...")
    parser.add_argument("--disable-enrichment", action="store_true", help="...")
    parser.add_argument("--relevance-threshold", type=int, default=None, help="...")
    # ... +12 argumentos
    
    subparsers = parser.add_subparsers(dest="command")
    discover_parser = subparsers.add_parser("discover", help="...")
    discover_parser.add_argument("value", help="...")
    discover_parser.add_argument("--format", choices=["human", "short", "full"], ...)
    
    return parser

def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    
    if args.command == "discover":
        # ... lógica discover
        pass
    
    # ... 50+ linhas de override config
    if args.zips_dir:
        config.zips_dir = args.zips_dir
    if args.newsletters_dir:
        config.newsletters_dir = args.newsletters_dir
    # ... etc
    
    processor = UnifiedProcessor(config)
    results = processor.process_all(days=args.days)
    
    # Output feio
    print("\n" + "="*60)
    print("✅ COMPLETE")
    print("="*60 + "\n")
    print(f"Groups processed: {len(results)}")
    
    return 0
```

---

### Depois: Typer + Rich (60 linhas)

```python
# src/egregora/__main__.py (novo)

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from .config import PipelineConfig
from .processor import UnifiedProcessor
from .discover import discover_identifier

# Instância global
app = typer.Typer(
    name="egregora",
    help="🗣️ Gera newsletters diárias a partir de exports do WhatsApp",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()


# ============================================================================
# COMANDO PRINCIPAL: process
# ============================================================================

@app.command(name="process")
def process_groups(
    # Essenciais
    config_file: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Arquivo TOML de configuração")
    ] = None,
    
    zips_dir: Annotated[
        Optional[Path],
        typer.Option(help="Diretório com arquivos .zip do WhatsApp")
    ] = None,
    
    newsletters_dir: Annotated[
        Optional[Path],
        typer.Option(help="Diretório de saída para newsletters")
    ] = None,
    
    days: Annotated[
        int,
        typer.Option(help="Número de dias recentes a processar")
    ] = 2,
    
    # Flags comuns
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simula processamento sem executar")
    ] = False,
    
    list_groups: Annotated[
        bool,
        typer.Option("--list", "-l", help="Lista grupos descobertos e sai")
    ] = False,
    
    # Overrides opcionais
    model: Annotated[
        Optional[str],
        typer.Option(help="Override: modelo Gemini")
    ] = None,
    
    disable_enrichment: Annotated[
        bool,
        typer.Option("--no-enrich", help="Desativa enriquecimento de links")
    ] = False,
    
    disable_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Desativa cache persistente")
    ] = False,
):
    """
    Processa grupos do WhatsApp e gera newsletters diárias.
    
    [bold]Exemplos:[/bold]
    
      [cyan]egregora process[/cyan]                    # Processa tudo com defaults
      [cyan]egregora process --days 7[/cyan]            # Últimos 7 dias
      [cyan]egregora process --dry-run[/cyan]           # Preview sem executar
      [cyan]egregora process --config app.toml[/cyan]   # Usa configuração customizada
    """
    
    # Carregar configuração
    if config_file and config_file.exists():
        config = PipelineConfig.from_toml(config_file)
        # Overrides
        if zips_dir:
            config.zips_dir = zips_dir
        if newsletters_dir:
            config.newsletters_dir = newsletters_dir
        if model:
            config.model = model
    else:
        config = PipelineConfig.with_defaults(
            zips_dir=zips_dir,
            newsletters_dir=newsletters_dir,
            model=model,
        )
    
    # Aplicar flags
    if disable_enrichment:
        config.enrichment.enabled = False
    if disable_cache:
        config.cache.enabled = False
    
    processor = UnifiedProcessor(config)
    
    # Modo LIST
    if list_groups:
        _show_groups_table(processor)
        return
    
    # Modo DRY RUN
    if dry_run:
        _show_dry_run(processor, days)
        return
    
    # Processamento real
    _process_and_display(processor, days)


# ============================================================================
# COMANDO: discover
# ============================================================================

@app.command()
def discover(
    value: Annotated[
        str,
        typer.Argument(help="Telefone ou apelido para anonimizar")
    ],
    
    format: Annotated[
        str,
        typer.Option(help="Formato de saída")
    ] = "human",
    
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Imprime apenas o identificador")
    ] = False,
):
    """
    Calcula o identificador anônimo para um telefone ou apelido.
    
    [bold]Exemplos:[/bold]
    
      [cyan]egregora discover "+5511999999999"[/cyan]
      [cyan]egregora discover "João Silva" --format short[/cyan]
      [cyan]egregora discover "+5511999999999" --quiet[/cyan]
    """
    
    try:
        result = discover_identifier(value)
    except ValueError as exc:
        console.print(f"[red]❌ Erro:[/red] {exc}")
        raise typer.Exit(code=1)
    
    if quiet:
        console.print(result.get(format))
    else:
        # Output bonito com Rich
        panel = Panel(
            f"[bold cyan]{result.get(format)}[/bold cyan]",
            title=f"🔐 Identificador Anônimo ({format})",
            border_style="cyan",
        )
        console.print(panel)
        
        # Mostrar todos os formatos
        table = Table(title="Formatos Disponíveis", show_header=True)
        table.add_column("Formato", style="cyan")
        table.add_column("Identificador", style="green")
        
        for fmt in ["human", "short", "full"]:
            table.add_row(fmt, result.get(fmt))
        
        console.print(table)


# ============================================================================
# HELPERS COM RICH
# ============================================================================

def _show_groups_table(processor: UnifiedProcessor):
    """Mostra grupos descobertos em tabela formatada."""
    
    groups = processor.list_groups()
    
    table = Table(
        title="📁 Grupos Descobertos",
        show_header=True,
        header_style="bold magenta",
    )
    
    table.add_column("Tipo", style="cyan", width=8)
    table.add_column("Nome", style="white")
    table.add_column("Slug", style="dim")
    table.add_column("Exports", justify="right", style="green")
    table.add_column("Período", style="yellow")
    
    for slug, info in sorted(groups.items()):
        tipo_icon = "📺 Virtual" if info['type'] == 'virtual' else "📝 Real"
        nome = info['name']
        exports = str(info['export_count'])
        periodo = f"{info['date_range'][0]} → {info['date_range'][1]}"
        
        table.add_row(tipo_icon, nome, slug, exports, periodo)
    
    console.print(table)


def _show_dry_run(processor: UnifiedProcessor, days: int):
    """Mostra preview do que seria processado."""
    
    console.print("\n")
    console.print(Panel(
        "[bold yellow]🔍 Modo DRY RUN[/bold yellow]\n"
        "Mostrando o que seria processado sem executar",
        border_style="yellow"
    ))
    
    groups = processor.list_groups()
    
    total_newsletters = 0
    
    for slug, info in sorted(groups.items()):
        potential_days = min(days, info['export_count'])
        total_newsletters += potential_days
        
        console.print(f"\n[cyan]📝 {info['name']}[/cyan] ([dim]{slug}[/dim])")
        console.print(f"   Exports disponíveis: {info['export_count']}")
        console.print(f"   Newsletters a gerar: [green]{potential_days}[/green]")
    
    console.print(f"\n[bold]Total:[/bold] {total_newsletters} newsletters seriam geradas")
    console.print("[dim]💡 Remova --dry-run para executar de verdade[/dim]\n")


def _process_and_display(processor: UnifiedProcessor, days: int):
    """Processa grupos e mostra resultado formatado."""
    
    console.print("\n")
    console.print(Panel(
        "[bold green]🚀 Processando Grupos[/bold green]",
        border_style="green"
    ))
    
    # TODO: Adicionar progress bar aqui com Rich.progress
    results = processor.process_all(days=days)
    
    # Sumário formatado
    total = sum(len(v) for v in results.values())
    
    table = Table(
        title="✅ Processamento Completo",
        show_header=True,
        header_style="bold green",
    )
    
    table.add_column("Grupo", style="cyan")
    table.add_column("Newsletters", justify="right", style="green")
    
    for slug, newsletters in sorted(results.items()):
        table.add_row(slug, str(len(newsletters)))
    
    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", style="bold")
    
    console.print("\n")
    console.print(table)
    console.print("\n")


# ============================================================================
# ENTRY POINT
# ============================================================================

def run():
    """Entry point usado pelo console script."""
    app()


if __name__ == "__main__":
    run()
```

---

## 📊 Comparação Antes vs Depois

| Aspecto | argparse | Typer + Rich |
|---------|----------|--------------|
| **Linhas de código** | ~150 | ~60 (-60%) |
| **Type hints** | Manual com `type=Path` | Nativo com `Annotated` |
| **Help text** | Texto plano | Markdown + cores |
| **Validação** | Manual | Automática |
| **Output** | `print()` feio | Tabelas, panels, cores |
| **Subcomandos** | Verboso | Decoradores `@app.command()` |
| **Shell completion** | Manual | Automático |
| **Manutenibilidade** | ⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🎨 Exemplos de Output com Rich

### Comando: `egregora process --list`

```
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Tipo     ┃ Nome               ┃ Slug         ┃ Exports ┃ Período             ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ 📝 Real  │ RC LatAm           │ rc-latam     │      15 │ 2025-01-01 → 2025… │
│ 📝 Real  │ Tech Discussions   │ tech-disc    │       8 │ 2025-01-10 → 2025… │
│ 📺 Virtual│ Merged Global      │ merged-glob  │      23 │ 2025-01-01 → 2025… │
└──────────┴────────────────────┴──────────────┴─────────┴─────────────────────┘
```

### Comando: `egregora discover "+5511999999999"`

```
╭─────────── 🔐 Identificador Anônimo (human) ────────────╮
│                      Member-A1B2                        │
╰─────────────────────────────────────────────────────────╯

                  Formatos Disponíveis                  
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Formato  ┃ Identificador                             ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ human    │ Member-A1B2                               │
│ short    │ User-A1B2                                 │
│ full     │ Member-a1b2c3d4-e5f6-7890-abcd-ef1234567890│
└──────────┴───────────────────────────────────────────┘
```

### Comando: `egregora process --dry-run`

```
╭─────────────────────────────────────────────╮
│       🔍 Modo DRY RUN                       │
│                                             │
│ Mostrando o que seria processado sem       │
│ executar                                    │
╰─────────────────────────────────────────────╯

📝 RC LatAm (rc-latam)
   Exports disponíveis: 15
   Newsletters a gerar: 2

📝 Tech Discussions (tech-disc)
   Exports disponíveis: 8
   Newsletters a gerar: 2

Total: 4 newsletters seriam geradas
💡 Remova --dry-run para executar de verdade
```

### Comando: `egregora process`

```
╭──────────────────────────╮
│  🚀 Processando Grupos   │
╰──────────────────────────╯

[... progress bar aqui ...]

          ✅ Processamento Completo          
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Grupo            ┃ Newsletters ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ rc-latam         │           2 │
│ tech-disc        │           2 │
│ TOTAL            │           4 │
└──────────────────┴─────────────┘
```

---

## 🚀 Recursos Avançados do Typer

### 1. Auto-completion

```bash
# Instalar completion
egregora --install-completion

# Agora funciona:
egregora pro<TAB>  → egregora process
egregora process --<TAB>  → mostra todas as opções
```

### 2. Validação automática

```python
# Typer valida automaticamente
@app.command()
def process(
    days: Annotated[int, typer.Option(min=1, max=365)] = 2,
):
    """Days deve ser 1-365"""
    pass

# Uso:
$ egregora process --days 0
# Error: Invalid value for '--days': 0 is not in the range 1<=x<=365
```

### 3. Callbacks customizados

```python
def validate_config_file(value: Optional[Path]) -> Optional[Path]:
    """Valida que arquivo de config existe."""
    if value and not value.exists():
        raise typer.BadParameter(f"Config file not found: {value}")
    return value

@app.command()
def process(
    config_file: Annotated[
        Optional[Path],
        typer.Option(callback=validate_config_file)
    ] = None,
):
    pass
```

### 4. Rich progress bars

```python
from rich.progress import Progress, SpinnerColumn, TextColumn

def _process_and_display(processor: UnifiedProcessor, days: int):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        task = progress.add_task("Processando grupos...", total=None)
        results = processor.process_all(days=days)
        progress.update(task, completed=True)
    
    # Mostrar resultados...
```

---

## 📝 Plano de Migração

### Fase 1: Setup (30 min)

```bash
# 1. Adicionar dependências
uv add typer rich

# 2. Criar backup do __main__.py atual
cp src/egregora/__main__.py src/egregora/__main__.py.bak

# 3. Validar imports
python -c "import typer, rich; print('OK')"
```

### Fase 2: Refatorar comando principal (2 horas)

1. Substituir `build_parser()` por `app = typer.Typer()`
2. Converter `main()` para `@app.command(name="process")`
3. Migrar argumentos para `Annotated` parameters
4. Remover lógica de override manual (Typer faz automaticamente)

### Fase 3: Adicionar discover command (1 hora)

1. Criar `@app.command() def discover(...)`
2. Adicionar formatação Rich no output

### Fase 4: Melhorar outputs (2 horas)

1. Substituir `print()` por `console.print()`
2. Criar `_show_groups_table()` com Rich Table
3. Criar `_show_dry_run()` com Rich Panel
4. Adicionar progress bar em `_process_and_display()`

### Fase 5: Dry run mode (1 hora)

1. Adicionar flag `--dry-run`
2. Implementar `_show_dry_run()` helper

### Fase 6: Testes e validação (2 horas)

```python
# tests/test_cli_typer.py

from typer.testing import CliRunner
from egregora.__main__ import app

runner = CliRunner()

def test_process_help():
    result = runner.invoke(app, ["process", "--help"])
    assert result.exit_code == 0
    assert "Processa grupos" in result.stdout

def test_discover_command():
    result = runner.invoke(app, ["discover", "+5511999999999"])
    assert result.exit_code == 0
    assert "Member-" in result.stdout

def test_dry_run():
    result = runner.invoke(app, ["process", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.stdout
```

### Fase 7: Documentação (1 hora)

```markdown
# README.md atualizado

## 🚀 Uso

### Processamento básico
```bash
egregora process
```

### Com configuração customizada
```bash
egregora process --config app.toml --days 7
```

### Preview antes de executar
```bash
egregora process --dry-run
```

### Listar grupos descobertos
```bash
egregora process --list
```

### Calcular identificador anônimo
```bash
egregora discover "+5511999999999"
```

---

## 🎯 Benefícios Finais

### Para Usuários
- ✅ CLI mais intuitivo e bonito
- ✅ Feedback visual claro (cores, tabelas)
- ✅ Help text rico e informativo
- ✅ Dry-run nativo para preview seguro
- ✅ Shell completion automático

### Para Desenvolvedores
- ✅ 60% menos código (~90 linhas removidas)
- ✅ Type safety nativo
- ✅ Validação automática
- ✅ Testes mais simples com `CliRunner`
- ✅ Manutenção muito mais fácil

### Para o Projeto
- ✅ Stack moderna (Typer + Rich são padrão industry)
- ✅ Melhor experiência de onboarding
- ✅ Output profissional
- ✅ Redução de bugs (validação automática)

---

## 📋 Checklist de Implementação

### Preparação
- [ ] `uv add typer rich`
- [ ] Backup de `__main__.py`
- [ ] Ler docs: https://typer.tiangolo.com/
- [ ] Ler docs: https://rich.readthedocs.io/

### Implementação
- [ ] Refatorar comando `process`
- [ ] Migrar comando `discover`
- [ ] Adicionar `--dry-run`
- [ ] Implementar helpers com Rich (tables, panels)
- [ ] Adicionar progress bars

### Validação
- [ ] Testar todos os comandos manualmente
- [ ] Escrever testes com `CliRunner`
- [ ] Validar shell completion
- [ ] Testar em diferentes terminais

### Documentação
- [ ] Atualizar README com novos exemplos
- [ ] Atualizar help texts
- [ ] Adicionar screenshots (opcional)
- [ ] Atualizar Copilot instructions

### Deploy
- [ ] Remover `__main__.py.bak`
- [ ] Git commit com mensagem descritiva
- [ ] Criar release notes mencionando novo CLI

---

## 💡 Extras Opcionais

### 1. Temas customizados

```python
from rich.theme import Theme

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
})

console = Console(theme=custom_theme)

# Uso
console.print("[info]Processando...[/info]")
console.print("[success]✅ Completo![/success]")
```

### 2. Logging com Rich

```python
from rich.logging import RichHandler
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)

logger = logging.getLogger("egregora")
```

### 3. Configuração interativa

```python
from rich.prompt import Prompt, Confirm

def configure_interactive():
    """Wizard de configuração interativa."""
    
    zips_dir = Prompt.ask(
        "Diretório dos ZIPs",
        default="data/whatsapp_zips"
    )
    
    enable_enrichment = Confirm.ask(
        "Ativar enriquecimento de links?",
        default=True
    )
    
    # Gerar egregora.toml
    ...
```

---

## 🎓 Recursos para Aprender

- **Typer docs:** https://typer.tiangolo.com/
- **Rich docs:** https://rich.readthedocs.io/
- **Tutorial Typer + Rich:** https://www.youtube.com/watch?v=VGY9VSlzB84
- **Exemplos reais:** https://github.com/tiangolo/typer/tree/master/docs_src

---

**Conclusão:** A migração para Typer + Rich é uma evolução natural que traz enormes benefícios com esforço relativamente baixo (3-5 dias). O resultado é um CLI moderno, profissional e muito mais fácil de manter.

**Recomendação:** Implementar junto com a simplificação do CLI (sugestão #1) para maximizar o impacto da refatoração.
