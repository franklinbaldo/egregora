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

## 2. Ensaiar com Dry-Run

Veja rapidamente quais datas seriam processadas sem gerar arquivos:

```bash
uv run egregora pipeline data/whatsapp_zips/*.zip --days 2 --dry-run --show
```

Saída típica:

```
📥 Ingerindo exports...
🧮 Gerando embeddings com Gemini...
📝 Gerando posts...
╭─ Prévia 2025-10-10 ─╮
│ ...markdown renderizado... │
╰────────────────────╯
╭─ Prévia 2025-10-11 ─╮
│ ...markdown renderizado... │
╰────────────────────╯
```

O modo `--show` imprime a versão resumida de cada dia, útil para validar anonimização e tom antes de gravar em disco.【F:src/egregora/__main__.py†L188-L212】

## 3. Gerar Posts e Prévia MkDocs

```bash
uv run egregora pipeline data/whatsapp_zips/*.zip \
  --days 2 \
  --workspace tmp/egregora \
  --build-static \
  --preview
```

Progresso esperado:

```
📥 Ingerindo exports...
🧮 Gerando embeddings com Gemini...
💾 Dataset consolidado em tmp/egregora/grupo-teste-20251011.parquet
🧠 Construindo índice DuckDB em memória...
📝 Gerando posts...
╭─ Posts geradas ─────╮
│ Data       │ Arquivo │
│ 2025-10-10 │ docs/posts/2025-10-10-grupo-teste.md │
│ 2025-10-11 │ docs/posts/2025-10-11-grupo-teste.md │
╰────────────────────╯
✅ Site estático atualizado com sucesso.
🌐 Servindo MkDocs em http://127.0.0.1:8001 (Ctrl+C para sair)
```

Enquanto o servidor MkDocs estiver ativo você verá uma prévia atualizada no navegador. Use `Ctrl+C` para encerrar quando terminar.【F:src/egregora/__main__.py†L168-L212】

## 4. Visualizar Resultado

```bash
# Ver post gerado
cat docs/posts/2025-10-11-grupo-teste.md
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

Se usou `--preview`, o servidor MkDocs já estará em execução em `http://127.0.0.1:8001`. Caso queira reconstruir manualmente depois:

```bash
uv run mkdocs build
uv run mkdocs serve
```

## Próximos Passos

<div class="grid cards" markdown>

-   :material-cog: **[Configurar](rag-setup.md)**

    Ajuste RAG, Profiles, Cache

-   :material-book-open: **[Guias](../blog/index.md)**

    Aprenda recursos avançados

-   :material-frequently-asked-questions: **[FAQ](../blog/posts/2025-10-13-egregora-1-0.md)**

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
    uv run egregora pipeline data/whatsapp_zips/*.zip --days 1
    ```
