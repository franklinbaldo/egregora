# Plano: visionary - Sprint 3

**Persona:** visionary
**Sprint:** 3
**Criado em:** 2026-01-22
**Prioridade:** Alta

## Objetivos

Descreva os principais objetivos para este sprint:

- [ ] Finalizar integração de `CodeReferenceDetector` no pipeline principal (Enricher Agent) (RFC 027).
- [ ] Iniciar design da API do Universal Context Layer (RFC 026).
- [ ] Criar "Hello World" Plugin para VS Code que consulta a API local.

## Dependências

Liste dependências de trabalho de outras personas:

- **architect:** Revisão do design da API do Context Layer (REST vs MCP).
- **sheriff:** Setup de testes de integração para o plugin VS Code.

## Contexto

Explique o contexto e raciocínio por trás deste plano:

Com a base de dados histórica (RFC 027) funcionando, podemos começar a expor esses dados para ferramentas externas (RFC 026). O plugin VS Code servirá como prova de conceito para a visão "Ubiquitous Memory".

## Entregáveis Esperados

1. Feature RFC 027 completa e mergeada (Links históricos no blog).
2. OpenAPI Spec para Context Layer API.
3. Repositório `egregora-vscode` com plugin básico.

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Complexidade da API | Média | Alto | Adotar padrão MCP (Model Context Protocol) para simplificar |
| Overhead do Plugin | Baixa | Baixo | Manter plugin "dumb", lógica no servidor Egregora |

## Colaborações Propostas

- **Com architect:** Definição dos endpoints da API.
- **Com forge:** Ajuda com TypeScript para o plugin VS Code.

## Notas Adicionais

Sprint crítico para transição de "Gerador" para "Plataforma".
