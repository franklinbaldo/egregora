# Arquitetura do Diretório `.team/`

Este documento descreve a estrutura e o funcionamento do diretório `.team/` no repositório **Egregora**, detalhando como o agente Jules é orquestrado, como seu estado é mantido e como as personas são configuradas.

## 1. Visão Geral

O diretório `.team/` é o centro de inteligência e automação do projeto. Ele contém não apenas as definições das personas (agentes especializados), mas também toda a lógica de agendamento, gerenciamento de sprints e persistência de estado das execuções.

## 2. Estrutura de Diretórios

| Caminho | Descrição |
| :--- | :--- |
| `.team/repo/` | Código Python do Jules, organizado por CLI, Core, Features e Scheduler. |
| `.team/repo/cli/` | CLIs Typer (schedule, autofix, feedback, sync, job, my-tools). |
| `.team/repo/core/` | Cliente da API Jules, helpers GitHub e exceções. |
| `.team/repo/features/` | Auto-fix, feedback loop, mail (local/S3), polling e sessão. |
| `.team/repo/scheduler/` | Engine, compatibilidade legacy, managers e estado persistente. |
| `.team/repo/templates/` | Templates Jinja2 (base, blocks, partials, prompts). |
| `.team/personas/` | Personas e seus prompts (`prompt.md`/`prompt.md.j2`) e journals. |
| `.team/sprints/` | Planejamentos e feedbacks organizados por ciclos de sprint. |
| `.team/mail/` | Maildir local usado pelo sistema de mensagens. |
| `.team/state/` | Estado local de reconciliacao (ex: `reconciliation.json`). |
| `.team/tasks/` | Gerenciamento de tarefas (todo, done, canceled) em Markdown. |
| `.team/cycle_state.json` | Estado persistente do ciclo (multi-track). |
| `.team/schedules.toml` | Configuração de agendamento (Cron) e tracks do ciclo. |

## 3. Gerenciamento de Estado (`cycle_state.json`)

O arquivo `cycle_state.json` foi recentemente refatorado para garantir robustez e rastreabilidade total.

### Estrutura do JSON
O histórico agora utiliza um **dicionário com chaves inteiras sequenciais** para evitar sobrescritas acidentais e permitir o crescimento infinito do log.

```json
{
  "history": {
    "0": {
      "persona_id": "curator",
      "session_id": "12345...",
      "pr_number": 2400,
      "created_at": "2026-01-14T...",
      "track": "default"
    },
    "1": { ... }
  },
  "tracks": {
    "default": {
      "persona_id": "refactor",
      "session_id": "67890...",
      "pr_number": null,
      "updated_at": "2026-01-14T..."
    }
  }
}
```

### Lógica de Persistência
- **Ordenação**: Antes de salvar, o dicionário de histórico é ordenado numericamente pelas chaves.
- **Nomenclatura**: Variáveis internas e propriedades do objeto de estado foram simplificadas, removendo o prefixo `last_` (ex: `persona_id` em vez de `last_persona_id`).
- **Compatibilidade**: O carregador (`load`) converte automaticamente formatos antigos (listas) para a nova estrutura de dicionário.
- **Multi-track**: O estado também mantém `tracks` com a ultima sessao por trilha.

## 4. Personas e Ciclos

As personas são definidas em `.team/personas/{id}/prompt.md` ou `.team/personas/{id}/prompt.md.j2`. O Jules opera em dois modos principais definidos no `schedules.toml`:

1.  **Modo Ciclo Paralelo (Parallel Cycle Mode)**: Tracks independentes; cada track executa personas sequencialmente e só avança após a sessao anterior encerrar.
2.  **Modo Agendado (Scheduled Mode)**: Utiliza expressões Cron para disparar personas específicas em horários determinados.

## 5. Fluxo de Execução

1.  O **Scheduler** carrega o `cycle_state.json` (via `PersistentCycleState`).
2.  Identifica a próxima persona por track e verifica o estado da sessao anterior.
3.  Dispara uma nova sessao via API, criando um branch específico para a persona.
4.  Atualiza o `cycle_state.json` e, quando configurado, persiste no branch `jules`.

## 6. Sprints e Tarefas

O sistema de sprints em `.team/sprints/` organiza o trabalho em blocos temporais, onde cada persona contribui com planos e feedbacks. As tarefas em `.team/tasks/` servem como a "memória de curto prazo" do que precisa ser feito, sendo consumidas pelas personas durante suas execuções.
