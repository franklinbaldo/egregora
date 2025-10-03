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

Retorne o JSON completo do novo perfil:

{{
    "worldview_summary": "Parágrafo incorporando como {member_id} se posiciona nas discussões do grupo...",
    "core_interests": {{}},
    "thinking_style": "Incluir como {member_id} desenvolve ideias em interação...",
    "values_and_priorities": [],
    "expertise_areas": {{}},
    "contribution_style": "Detalhar COMO {member_id} contribui: timing, resposta a contextos, impacto...",
    "argument_patterns": ["Incluir como argumenta EM RESPOSTA a outros"],
    "questioning_approach": "Como e quando faz perguntas...",
    "intellectual_influences": [],
    "aligns_with": ["Member-XXX (em que contextos/tópicos?)"],
    "debates_with": ["Member-XXX (sobre o quê? Como debate?)"],
    "recent_shifts": [],
    "growing_interests": [],
    "interaction_patterns": {{
        "participation_timing": "Quando tende a participar?",
        "response_style": "Como responde a diferentes estímulos?",
        "influence_on_group": "Que papel desempenha nas discussões?"
    }}
}}
"""
