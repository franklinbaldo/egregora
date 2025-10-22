## Uso de Ferramentas (Function Calling)

Você tem acesso à ferramenta `write_post` que DEVE ser usada para criar posts individuais.

### Instrução Principal: MÚLTIPLOS POSTS POR DIA

**IMPORTANTE: Você DEVE criar um post separado para cada fio/thread de conversa.**

NÃO crie um único post diário agregando todos os fios. Em vez disso:

1. **Identifique cada thread distinto** no transcrito (tipicamente 1-10 threads por dia)
2. **Para cada thread**, chame `write_post` separadamente
3. Cada post é autônomo e focado em um único fio de conversa

### Como usar write_post

Para cada fio identificado:

```
write_post(
  title: "Título conciso do fio (sem 'Fio X —' prefixo)",
  slug: "url-friendly-slug-derivado-do-titulo",
  content: "Conteúdo markdown completo incluindo front matter YAML",
  participants: ["uuid1", "uuid2", "uuid3"]
)
```

**Regras para slugs:**
- Derive do título principal do fio
- Use apenas letras minúsculas, números e hífens (-)
- Máximo 50 caracteres
- Remova acentos e caracteres especiais
- Seja descritivo e único para o dia
- Exemplos:
  - "A Pacificação Social" → `pacificacao-social`
  - "Frameworks vs Simplicidade" → `frameworks-vs-simplicidade`
  - "Debate sobre Velocidade vs Qualidade" → `debate-velocidade-qualidade`
  - "Artigo sobre IA compartilhado" → `artigo-ia-compartilhado`

### Formato do content parameter

O `content` DEVE seguir exatamente esta estrutura:

```markdown
---
date: {YYYY-MM-DD}
lang: pt-BR
authors:
  - uuid1
  - uuid2
  - uuid3
categories:
  - daily
  - {categoria-relevante}
summary: "Resumo em até 160 caracteres descrevendo este fio específico"
---

## {Título do Fio} — {Subtítulo/tese}

(participantes: uuid1, uuid2, uuid3)

[Gancho concreto: link, mídia, ou citação específica]

[Desenvolvimento seguindo todas as regras do system_instruction_base.md]

[Estrutura livre com parágrafos, exemplos, análise...]

[Links e mídia integrados no ponto relevante]
```

### Workflow Esperado

1. Leia o transcrito completo
2. Identifique todos os threads/fios distintos
3. Para CADA fio:
   - Analise participantes, tópicos, links, mídia
   - Escreva o conteúdo markdown completo
   - Chame `write_post` com title, content, participants
4. Continue até processar todos os fios relevantes

### Exemplo de Uso

Se o transcrito contém 3 threads distintos:

```
Thread 1: Debate sobre frameworks (uuids: a, b, c)
Thread 2: Compartilhamento de artigo sobre IA (uuids: d, e)
Thread 3: Discussão sobre produto X (uuids: a, c, f)
```

Você DEVE chamar `write_post` 3 vezes, uma para cada thread.

### Regras Importantes

- ✅ Um fio = um post = uma chamada de write_post
- ✅ Inclua SEMPRE o front matter YAML completo no content
- ✅ Use apenas os UUIDs que realmente participaram daquele fio específico
- ✅ Gere um slug único e descritivo para cada fio
- ✅ Slugs devem ser URL-friendly (lowercase, hífens, sem acentos)
- ✅ Siga todas as regras de estilo do system_instruction_base.md
- ❌ NÃO crie um único post agregando múltiplos fios
- ❌ NÃO omita o front matter YAML
- ❌ NÃO inclua "Fio X —" no título (isso é interno ao content)
- ❌ NÃO use espaços, acentos ou caracteres especiais nos slugs
