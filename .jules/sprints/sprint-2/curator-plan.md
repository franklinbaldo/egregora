# Plano: Curator - Sprint 2

**Persona:** curator  
**Sprint:** 2  
**Criado em:** 2026-01-07 (durante sprint-1)
**Prioridade:** Alta  

## Objetivos

O curator tem como missão manter o repositório organizado e saudável. Para o sprint-2, os objetivos são:

- [ ] Implementar sistema de labels estruturado
- [ ] Categorizar todas as issues abertas (150+)
- [ ] Criar documento de processo de triagem
- [ ] Identificar e fechar issues duplicadas ou obsoletas

## Dependências

As seguintes dependências foram identificadas:

- **refactor:** Aguardando refatoração do módulo de issues para facilitar automação de labels
- **docs_curator:** Coordenar sobre documentação do processo de triagem
- **sheriff:** Alinhar sobre políticas de fechamento de issues

## Contexto

Durante o sprint-1, foi identificado que o repositório possui mais de 150 issues abertas sem organização clara. Muitas issues não têm labels, algumas são duplicadas, e outras estão obsoletas. Isso dificulta a priorização e o trabalho de outras personas.

A implementação de um sistema de labels estruturado e a categorização das issues existentes vai melhorar significativamente a eficiência do trabalho de todas as personas, especialmente builder, visionary e taskmaster.

## Entregáveis Esperados

1. **Sistema de Labels:** Conjunto completo de labels criadas no GitHub (tipo, prioridade, área, status)
2. **Issues Categorizadas:** Todas as 150+ issues com labels apropriadas
3. **Documento de Processo:** Markdown descrevendo como fazer triagem de novas issues
4. **Limpeza:** Lista de issues fechadas (duplicadas/obsoletas) com justificativa

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Volume de issues muito alto | Alta | Médio | Priorizar issues mais recentes e ativas |
| Conflito sobre fechamento | Média | Alto | Consultar sheriff antes de fechar issues controversas |
| Labels inconsistentes | Baixa | Médio | Revisar com docs_curator antes de aplicar em massa |

## Colaborações Propostas

- **Com refactor:** Após refatoração do módulo de issues, implementar automação de labels
- **Com docs_curator:** Revisar documento de processo e incluir na documentação oficial
- **Com sheriff:** Definir políticas claras de fechamento de issues

## Notas Adicionais

Este trabalho vai beneficiar diretamente o trabalho do taskmaster (priorização) e do organizer (estruturação). Considerar criar um dashboard de métricas de issues após a categorização.
