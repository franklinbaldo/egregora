# Seu Primeiro Post

Vamos gerar sua primeira post em 5 minutos.

## 1. Preparar Export do WhatsApp

### Exportar Conversa

No WhatsApp:

1. Abra o grupo
2. Toque em ⋮ (três pontos) → **Mais** → **Exportar conversa**
3. Escolha **Incluir mídia** (opcional)
4. Salve o arquivo `.zip`

### Organizar Arquivos

```bash
# Criar diretório
mkdir -p data/whatsapp_zips

# Mover export
mv ~/Downloads/WhatsApp*.zip data/whatsapp_zips/
```

## 2. Gerar Post (Modo Dry-Run)

Primeiro, veja o que seria processado:

```bash
uv run egregora process data/whatsapp_zips/*.zip --dry-run
```

Saída esperada:

```
🔍 Modo DRY RUN

📝 Rationality Club (rationality-club)
   Exports disponíveis: 1
   Intervalo: 2025-03-02 → 2025-10-11
   Será gerado: 2025-10-10, 2025-10-11

📊 Estimativa:
   Total: 2 posts
   API calls: ~25
   Tempo: ~2 minutos
```

## 3. Gerar Posts

```bash
# Gerar últimos 2 dias
uv run egregora process data/whatsapp_zips/*.zip --days 2
```

Progresso:

```
📝 Processing: Rationality Club
  Processing 2025-10-10...
    132 messages from 7 participants
    [Enriquecimento] 2/3 itens relevantes
    [RAG] Nenhum contexto histórico (primeira execução)
    ✅ data/rationality-club/posts/daily/2025-10-10.md

  Processing 2025-10-11...
    156 messages from 9 participants
    [Enriquecimento] 3/4 itens relevantes
    [RAG] 2 contextos históricos encontrados
    [Profiles] Context built for 5 participants
    👤 Updated: Member-ABCD (v1)
    👤 Updated: Member-EFGH (v1)
    ✅ data/rationality-club/posts/daily/2025-10-11.md
```

## 4. Visualizar Resultado

```bash
# Ver post gerado
cat data/rationality-club/posts/daily/2025-10-11.md
```

Você verá:

```markdown
---
title: "📩 Rationality Club — Diário de 2025-10-11"
date: 2025-10-11T00:00:00-04:00
lang: pt-BR
authors:
  - egregora
categories:
  - daily
  - rationality-club
---

## Fio 1 — Debates sobre Consciência Artificial

Retomamos a discussão iniciada ontem sobre...
```

## 5. Ver no Site

```bash
# Iniciar servidor local
uv run mkdocs serve

# Abrir no navegador
open http://localhost:8000
```

## Próximos Passos

<div class="grid cards" markdown>

-   :material-cog: **[Configurar](configuration.md)**

    Ajuste RAG, Profiles, Cache

-   :material-book-open: **[Guias](../guides/index.md)**

    Aprenda recursos avançados

-   :material-frequently-asked-questions: **[FAQ](../about/faq.md)**

    Perguntas frequentes

</div>

## Problemas Comuns

??? question "API Key inválida"
    ```
    RuntimeError: Defina GEMINI_API_KEY
    ```

    **Solução:** Verifique se a variável de ambiente está definida:
    ```bash
    echo $GEMINI_API_KEY
    ```

??? question "Nenhum grupo encontrado"
    ```
    Nenhum grupo foi encontrado
    ```

    **Solução:** Verifique se há `.zip` em `data/whatsapp_zips/`:
    ```bash
    ls -la data/whatsapp_zips/
    ```

??? question "Quota excedida"
    ```
    RESOURCE_EXHAUSTED: Quota exceeded
    ```

    **Solução:** Tier gratuito tem limite de 15 req/min. Espere ou reduza batch:
    ```bash
    uv run egregora process data/whatsapp_zips/*.zip --days 1
    ```
