# Plano: Curator - Sprint 3

**Persona:** curator
**Sprint:** 3
**Criado em:** 2026-01-09 (durante sprint-1)
**Prioridade:** Média

## Objetivos

Continuando o trabalho de aprimoramento da experiência do usuário, o sprint-3 se concentrará em refinar a arquitetura de informação do blog e melhorar a acessibilidade.

- [ ] **Melhorar a Mensagem de "Estado Vazio":** Refinar a mensagem na `index.md` quando ainda não há posts, tornando-a mais acolhedora e menos técnica.
- [ ] **Revisar a Estrutura de Navegação:** Avaliar a hierarquia da navegação principal (e.g., a proeminência do link "Media") e propor uma estrutura mais intuitiva.
- [ ] **Auditoria de Acessibilidade (A11y):** Realizar uma auditoria focada em acessibilidade, verificando o contraste das cores, a navegação pelo teclado e o uso de atributos ARIA. Criar tarefas para a `forge` para corrigir quaisquer problemas encontrados.
- [ ] **Investigar e Planejar "Posts Relacionados":** Pesquisar maneiras de implementar uma seção de "posts relacionados" de forma autônoma e criar uma tarefa de design/implementação detalhada.

## Dependências

- **forge:** Será necessário para implementar as tarefas que surgirem da auditoria de acessibilidade e das outras iniciativas de UX.

## Contexto

Com as melhorias de branding de alto impacto implementadas no sprint-2, o sprint-3 pode se concentrar em aspectos mais sutis, mas igualmente importantes, da experiência do usuário. Melhorar a primeira impressão (estado vazio), a facilidade de encontrar informações (navegação) e garantir que o site seja utilizável por todos (acessibilidade) são os próximos passos lógicos na evolução do design do produto.

## Entregáveis Esperados

1.  **Tarefa para "Estado Vazio":** Uma tarefa de UX detalhada para a `forge` com o novo texto e possivelmente um conceito visual para a página inicial sem posts.
2.  **Proposta de Navegação:** Um documento ou tarefa descrevendo a nova estrutura de navegação recomendada.
3.  **Relatório de Acessibilidade e Tarefas:** Um resumo dos problemas de acessibilidade encontrados e as tarefas correspondentes criadas para a `forge`.
4.  **Especificação de "Posts Relacionados":** Uma tarefa detalhada descrevendo como a funcionalidade de posts relacionados deve ser projetada e implementada.

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| A auditoria de acessibilidade revela problemas complexos | Média | Alto | Priorizar as correções mais impactantes e fáceis de implementar primeiro. |
| A implementação de "posts relacionados" é tecnicamente inviável de forma autônoma | Média | Médio | A tarefa inicial é de pesquisa e design, o que ajudará a identificar a viabilidade antes de qualquer trabalho de implementação. |
