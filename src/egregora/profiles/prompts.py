"""Prompt templates used by the profile updater."""

from __future__ import annotations

UPDATE_DECISION_PROMPT = """Você é um analista de perfis de participantes em grupos.

**PERFIL ATUAL de {member_display} ({member_id}):**
---
{current_profile}
---

**CONVERSA COMPLETA DE HOJE:**
---
{full_conversation}
---

**TAREFA**: Analise a **participação de {member_display} ({member_id})** na conversa acima.

Considere:
- O que {member_display} disse
- QUANDO {member_display} interveio (início, meio, fim de discussões?)
- Em RESPOSTA A QUÊ {member_display} participou
- Como OUTROS reagiram ao que {member_display} disse
- Se {member_display} iniciou, continuou ou encerrou threads
- Qualidade e impacto das contribuições no contexto geral

**Vale atualizar se:**
✅ Demonstrou novo insight ou perspectiva não capturada no perfil
✅ Interagiu de forma diferente do padrão usual
✅ Revelou nova expertise ou interesse em contexto
✅ Mudou dinâmica de discussão de forma notável
✅ Aprofundou significativamente algo já mencionado

**NÃO vale atualizar se:**
❌ Participação consistente com perfil atual
❌ Mensagens rotineiras ou superficiais
❌ Apenas concordâncias/curtidas sem adicionar substância
❌ Participação tangencial ao tema principal

Retorne APENAS um JSON:
{{
    "should_update": true/false,
    "reasoning": "Explicação considerando o CONTEXTO da conversa (2-3 frases)",
    "participation_highlights": [
        "Destaque 1 da participação em contexto",
        "Destaque 2 da participação em contexto"
    ],
    "interaction_insights": [
        "Como {member_display} interagiu com outros hoje",
        "Padrão de participação observado"
    ]
}}
"""


PROFILE_REWRITE_PROMPT = """Você é um analista experiente de perfis intelectuais.

Você vai REESCREVER COMPLETAMENTE o perfil de {member_display} ({member_id}).

**PERFIL ANTERIOR:**
---
{old_profile}
---

**CONVERSAS RECENTES (últimas 5 sessões, incluindo hoje) para {member_display}:**

{recent_conversations}

**PARTICIPAÇÃO DE {member_display} EM DESTAQUE:**
{participation_highlights}

**INSIGHTS DE INTERAÇÃO:**
{interaction_insights}

**CONTEXTO IMPORTANTE:**
Você está vendo as conversas COMPLETAS, não apenas as mensagens de {member_display} ({member_id}).
Isso permite analisar:
- Como {member_display} responde a diferentes tópicos e pessoas
- Quando e por que {member_display} escolhe participar
- Como as contribuições de {member_display} influenciam o grupo
- Padrões de colaboração, debate e concordância

**TAREFA**:
Reescreva o perfil COMPLETO do zero, incorporando:
1. Tudo que ainda é válido do perfil anterior
2. Novas informações das conversas recentes
3. Insights sobre COMO {member_display} participa (não só O QUÊ diz)
4. Dinâmica de interações com outros membros

**IMPORTANTE:**
- Mantenha tom respeitoso e admirativo
- Seja específico citando CONTEXTO das participações
- Documente evolução se houver
- Destaque qualidade das contribuições NO CONTEXTO do grupo

Retorne APENAS um texto em Markdown seguindo exatamente esta estrutura:

# Perfil Analítico: {member_display} ({member_id})

## Visão Geral
Parágrafo único resumindo a postura de {member_display} nas discussões recentes e o impacto nas decisões do grupo.

## Participação Recente
- Bullet destacando contribuições relevantes com contexto de datas ou tópicos
- Outro bullet observando interações com outros membros

## Estilo de Colaboração
Parágrafo descrevendo a forma de colaborar, responder e liderar conversas, incluindo o timing das participações.

## Observações Estratégicas
- Bullet com insights sobre interesses atuais
- Bullet com possíveis evoluções ou alertas

_Finalize com uma linha em itálico indicando que o texto foi gerado automaticamente pela data de hoje._
"""


PROFILE_APPEND_PROMPT = """Você é um analista cuidadoso encarregado de **apenas registrar acréscimos** em perfis existentes.

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
{{
  "updates": [
    {{
      "heading": "## Nome exato do heading",
      "content": "Texto a ser acrescentado (pode conter múltiplas linhas ou bullets)"
    }}
  ],
  "summary_addendum": "Frase opcional para anexar ao resumo geral (pode ser vazia)"
}}

Se não houver nada relevante para acrescentar, retorne `"updates": []`.
"""
