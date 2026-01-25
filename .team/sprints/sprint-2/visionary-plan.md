# Plano: visionary - Sprint 2

**Persona:** visionary
**Sprint:** 2
**Criado em:** 2026-01-22
**Prioridade:** Alta

## Objetivos

Descreva os principais objetivos para este sprint:

- [ ] Prototipar `CodeReferenceDetector` para detecção de paths e SHAs em mensagens de chat (RFC 027).
- [ ] Implementar POC de `GitHistoryResolver` para mapear Timestamp -> Commit SHA (RFC 027).
- [ ] Validar viabilidade de integração com Markdown do agente Writer.

## Dependências

Liste dependências de trabalho de outras personas:

- **builder:** Suporte para schema de cache de Git Lookups em DuckDB.
- **scribe:** Atualização da documentação para incluir nova feature de links históricos.

## Contexto

Explique o contexto e raciocínio por trás deste plano:

Após a aprovação do Quick Win (RFC 027), o foco é validar a tecnologia principal (Regex + Git CLI) antes de integrar totalmente ao pipeline. Precisamos garantir que a detecção seja precisa e a resolução de commits seja rápida.

## Entregáveis Esperados

1. Script Python `detect_refs.py` que extrai referências de um arquivo de texto.
2. Script Python `resolve_commit.py` que aceita data/hora e retorna SHA do repo local.
3. Relatório de performance (tempo por lookup).

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Git Lookup lento | Alta | Médio | Implementar cache agressivo (DuckDB/Redis) |
| Ambiguidade de path | Média | Baixo | Linkar para tree root ou exibir warning se arquivo não existe |

## Colaborações Propostas

- **Com builder:** Definir schema da tabela `git_cache`.
- **Com artisan:** Revisar código do resolver para otimização.

## Notas Adicionais

Foco total na "Foundation" para o Context Layer.
