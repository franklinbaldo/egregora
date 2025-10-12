"""Prompt templates used by the profile updater."""

from __future__ import annotations

UPDATE_DECISION_PROMPT = """Você é um analista de perfis de participantes em grupos.

**PERFIL ATUAL de {member_id}:**
---
{current_profile}
---

**CONVERSA COMPLETA DE HOJE:**
---
{full_conversation}
---

**TAREFA**: Analise a **participação de {member_id}** na conversa acima.

Considere:
- O que {member_id} disse
- QUANDO {member_id} interveio (início, meio, fim de discussões?)
- Em RESPOSTA A QUÊ {member_id} participou
- Como OUTROS reagiram ao que {member_id} disse
- Se {member_id} iniciou, continuou ou encerrou threads
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

**CONTEXTO ADICIONAL:**
Este perfil será usado para:
- Gerar recomendações personalizadas
- Entender dinâmicas do grupo
- Identificar especialistas em tópicos
- Facilitar conexões entre membros

Por isso, atualizações devem capturar:
- Mudanças em expertise ou interesses
- Novos padrões de interação
- Evoluções em perspectivas
- Contribuições únicas ao grupo
{{
    "should_update": true/false,
    "reasoning": "Explicação considerando o CONTEXTO da conversa (2-3 frases)",
    "participation_highlights": [
        "Destaque 1 da participação em contexto",
        "Destaque 2 da participação em contexto"
    ],
    "interaction_insights": [
        "Como {member_id} interagiu com outros hoje",
        "Padrão de participação observado"
    ]
}}
"""


PROFILE_REWRITE_PROMPT = """Você é um analista experiente de perfis intelectuais.

Você vai REESCREVER COMPLETAMENTE o perfil de {member_id}.

**PERFIL ANTERIOR:**
---
{old_profile}
---

**CONVERSAS RECENTES (últimas 5 sessões, incluindo hoje):**

{recent_conversations}

**PARTICIPAÇÃO DE {member_id} EM DESTAQUE:**
{participation_highlights}

**INSIGHTS DE INTERAÇÃO:**
{interaction_insights}

**CONTEXTO IMPORTANTE:**
Você está vendo as conversas COMPLETAS, não apenas as mensagens de {member_id}.
Isso permite analisar:
- Como {member_id} responde a diferentes tópicos e pessoas
- Quando e por que {member_id} escolhe participar
- Como as contribuições de {member_id} influenciam o grupo
- Padrões de colaboração, debate e concordância

**TAREFA**:
Reescreva o perfil COMPLETO do zero, incorporando:
1. Tudo que ainda é válido do perfil anterior
2. Novas informações das conversas recentes
3. Insights sobre COMO {member_id} participa (não só O QUÊ diz)
4. Dinâmica de interações com outros membros

**IMPORTANTE:**
- Mantenha tom respeitoso e admirativo
- Seja específico citando CONTEXTO das participações
- Documente evolução se houver
- Destaque qualidade das contribuições NO CONTEXTO do grupo

Retorne APENAS um texto em Markdown seguindo exatamente esta estrutura:

# Perfil Analítico: {member_id}

## Visão Geral
Parágrafo único resumindo a postura de {member_id} nas discussões recentes e o impacto nas decisões do grupo.

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
