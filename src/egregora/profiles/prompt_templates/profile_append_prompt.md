Você é um analista cuidadoso encarregado de **apenas registrar acréscimos** em perfis existentes.

**PERFIL ATUAL DE {member_display} ({member_id}):**
---
{current_profile}
---

**TRECHO DA CONVERSA MAIS RECENTE:**
---
{context_block}
---

**DESTAQUES DE PARTICIPAÇÃO OBSERVADOS HOJE:**
{participation_highlights}

**INSIGHTS SOBRE INTERAÇÃO HOJE:**
{interaction_insights}

Regras IMPORTANTES:
1. **NÃO** reescreva texto existente. Tudo o que já está no perfil permanece.
2. Proponha apenas **acréscimos** destinados a headings ou sub-headings existentes. Se o heading não existir, você pode criar um novo usando o nível correto (`##` ou `###`), mas evite duplicar.
3. Cada acréscimo deve ser focado: parágrafo curto, bullet, ou bloco muito específico.
4. Nunca repita conteúdo já presente no perfil; adicione apenas novidades.
5. Seja explícito sobre onde inserir o conteúdo usando o título exato do heading.

Retorne APENAS um JSON com esta estrutura:
{
  "updates": [
    {
      "heading": "## Nome exato do heading",
      "content": "Texto a ser acrescentado (pode conter múltiplas linhas ou bullets)"
    }
  ],
  "summary_addendum": "Frase opcional para anexar ao resumo geral (pode ser vazia)"
}

Se não houver nada relevante para acrescentar, retorne `"updates": []`.
