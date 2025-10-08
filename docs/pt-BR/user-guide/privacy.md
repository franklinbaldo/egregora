# Privacidade e Anonimização

A Egrégora trata todo export do WhatsApp como dado sensível.
Antes de qualquer resumo, o pipeline anonimiza autores e reforça a política de
privacidade no prompt do modelo.
Assim garantimos posts legíveis sem expor nomes, telefones ou mensagens
privadas.

## Como protegemos os dados

1. **Anonimização determinística** — Cada telefone ou apelido vira um
   identificador estável, como `Member-3F1A`.
   O algoritmo usa UUIDv5, roda localmente e não grava nenhum mapeamento em
   disco.
2. **Prompt seguro** — As instruções enviadas ao Gemini reforçam que o modelo
   não deve citar nomes próprios, contatos diretos nem metadados
   identificáveis.
3. **Revisão opcional** — O CLI aceita `--disable-enrichment` para rodar só a
   extração e permite revisar o Markdown final antes de publicar.

### Exemplo visual

| Entrada original                     | Saída anonimizada           |
|--------------------------------------|-----------------------------|
| `João Silva: Enviou o PDF do evento` | `Member-3F1A: Enviou o PDF do evento` |

O identificador se repete em todas as mensagens dessa pessoa, preservando o
contexto para quem lê o post.

## Descobrir o próprio identificador

Qualquer participante pode descobrir seu ID localmente:

```bash
uv run egregora discover "+55 11 91234-5678"
```

Use `--quiet` para imprimir apenas o identificador.
O comando aceita telefones normalizados ou apelidos.

## Para quem desenvolve

- Ajuste os campos em `[anonymization]` no `egregora.toml` para trocar o
  formato (`human`, `short`, `full`).
- Ative a revisão dupla configurando `privacy.double_check_post = true` via
  `PipelineConfig`.
- Erros de rede no enrichment não expõem dados: o pipeline pode ser reexecutado
  sem reaplicar a anonimização.

Para mais detalhes técnicos, consulte
[Configuração](../developer-guide/config.md) e
[RAG](../developer-guide/rag.md).
