# Arquitetura do Diretório `.jules/`

Este documento descreve a estrutura e o funcionamento do diretório `.jules/` no repositório **Egregora**, detalhando como o agente Jules é orquestrado, como seu estado é mantido e como as personas são configuradas.

## 1. Visão Geral

O diretório `.jules/` é o centro de inteligência e automação do projeto. Ele contém não apenas as definições das personas (agentes especializados), mas também toda a lógica de agendamento, gerenciamento de sprints e persistência de estado das execuções.

## 2. Estrutura de Diretórios

| Caminho | Descrição |
| :--- | :--- |
| `.jules/jules/` | Contém o código Python que implementa o motor do Jules (Scheduler, Engine, Core). |
| `.jules/personas/` | Definições de cada persona, incluindo prompts base e diários de bordo (`journals`). |
| `.jules/sprints/` | Planejamentos e feedbacks organizados por ciclos de sprint. |
| `.jules/tasks/` | Gerenciamento de tarefas (todo, done, canceled) em formato Markdown. |
| `.jules/cycle_state.json` | Arquivo de estado persistente que rastreia o histórico de execuções. |
| `.jules/schedules.toml` | Configuração de agendamento (Cron) e definição da ordem do ciclo. |

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

## 4. Personas e Ciclos

As personas são definidas em `.jules/personas/{id}/prompt.md.j2`. O Jules opera em dois modos principais definidos no `schedules.toml`:

1.  **Modo Ciclo (Cycle Mode)**: Uma lista ordenada de personas que o Jules executa sequencialmente. Cada persona só inicia após a anterior completar sua tarefa (geralmente a criação de um PR).
2.  **Modo Agendado (Scheduled Mode)**: Utiliza expressões Cron para disparar personas específicas em horários determinados.

## 5. Fluxo de Execução

1.  O **Scheduler** carrega o `cycle_state.json`.
2.  Identifica a próxima persona baseada no histórico do `track` atual.
3.  Verifica se a sessão anterior foi concluída com sucesso.
4.  Dispara uma nova sessão via API, criando um branch específico para a persona.
5.  Atualiza o `cycle_state.json` com o novo `session_id` e persiste as mudanças no branch `jules`.

## 6. Sprints e Tarefas

O sistema de sprints em `.jules/sprints/` organiza o trabalho em blocos temporais, onde cada persona contribui com planos e feedbacks. As tarefas em `.jules/tasks/` servem como a "memória de curto prazo" do que precisa ser feito, sendo consumidas pelas personas durante suas execuções.
