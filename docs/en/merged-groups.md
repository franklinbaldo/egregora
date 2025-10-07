# Grupos Virtuais e Auto-Discovery

Esta nota descreve como o Egrégora detecta automaticamente exports do WhatsApp e
combina múltiplos grupos em "grupos virtuais" usando pandas/Polars. A versão
anterior deste documento era um plano de implementação; o código já está ativo e
os detalhes abaixo refletem o estado atual do projeto.

---

## 🧭 Visão Geral do Pipeline

```
ZIPs do WhatsApp → discover_groups → GroupSource → (opcional) merges virtuais → DataFrame → Transcript → Newsletter
```

1. `group_discovery.discover_groups` (`src/egregora/group_discovery.py`) varre
   `data/whatsapp_zips/` e produz uma lista ordenada de `WhatsAppExport` por
   slug.
2. `PipelineConfig.merges` (`src/egregora/config.py`) define combinações
   opcionais de grupos reais em um `MergeConfig` (com estilo de tag, emojis etc.).
3. `merger.create_virtual_groups` (`src/egregora/merger.py`) cria `GroupSource`
   virtuais reutilizando os exports originais e registrando avisos para fontes
   ausentes.
4. `transcript.load_source_dataframe` (`src/egregora/transcript.py`) usa Polars
   para ler e cachear os dados. Em grupos virtuais, `merge_with_tags` adiciona
   colunas com tags legíveis para diferenciar mensagens de cada origem.
5. `UnifiedProcessor` (`src/egregora/processor.py`) orquestra discovery, merges,
   filtros e geração das newsletters finais, expondo também o modo `--dry-run` e
   `--list` no CLI.
   

---

## 🔎 Auto-Discovery de Exports

- **Normalização segura**: `_extract_metadata` evita seguir symlinks, valida o
  ZIP e normaliza o nome do grupo com `_slugify`. Datas são inferidas do nome do
  arquivo, conteúdo ou timestamp como fallback.
- **`WhatsAppExport`**: contém caminho do ZIP, nome/slug do grupo, data do export,
  arquivo principal e anexos já filtrados de `__MACOSX`.
- Os exports ficam ordenados por data, garantindo que merges recebam uma sequência
  cronológica consistente.

---

## 🔀 Configurando Grupos Virtuais

Os merges são definidos no TOML (seção `[merges]`) ou diretamente via código.
Cada `MergeConfig` aceita:

- `source_groups`: lista de slugs reais a combinar.
- `tag_style`: `emoji`, `prefix` ou `brackets` para customizar o texto.
- `group_emojis`: mapa opcional `slug → emoji` quando o estilo for `emoji`.
- `model_override`: permite escolher outro modelo Gemini para aquele grupo.

No código, `create_virtual_groups` monta um `GroupSource` com `is_virtual=True`
para cada configuração válida.

### Tagueamento das mensagens

`merge_with_tags` usa Polars para criar a coluna `tagged_line` com o formato
escolhido. Para `emoji`, ele resolve o emoji por slug e insere na linha formatada
(`10:30 — User-A1B2 🌎: mensagem`). Outros estilos usam prefixo ou colchetes com o
nome do grupo.

Essas linhas tagueadas são usadas apenas em grupos virtuais; grupos reais usam a
coluna `original_line` preservada do parser.

---

## 📊 DataFrames e Cache

- `parser.parse_multiple` combina exports em um único `DataFrame` ordenado por
  timestamp, já com colunas `author`, `message`, `group_slug`, `group_name`.
  
- `transcript.load_source_dataframe` mantém um cache em memória (`_DATAFRAME_CACHE`)
  indexado por slug, caminhos de ZIP e opções de merge. Isso evita reprocessar os
  mesmos arquivos a cada newsletter ou chamada de dry-run.
- Estatísticas por dia (`get_stats_for_date`) e lista de datas disponíveis são
  derivadas direto do DataFrame filtrado, sem reabrir os ZIPs.

---

## 🚀 Uso no CLI

O comando `uv run egregora --list` mostra uma tabela Rich com os grupos reais e
virtuais detectados, incluindo quantos exports existem e o intervalo de datas.
Em `--dry-run`, `UnifiedProcessor.plan_runs` calcula as datas alvo e apresenta um
resumo antes da execução.

Para gerar newsletters de um merge, basta incluir a configuração correspondente
no TOML e executar `uv run egregora`. O pipeline ignora automaticamente os grupos
reais que fazem parte de merges quando `skip_real_if_in_virtual = true`.

---

## ✅ Benefícios atingidos

- **Zero duplicação**: merges reutilizam `WhatsAppExport` detectados, sem copiar
  arquivos ou gerar estrutura paralela.
- **Legibilidade**: mensagens tagueadas destacam a origem sem sacrificar o texto
  original. Real e virtual compartilham o mesmo fluxo downstream.
- **Manutenção simples**: adicionar um novo merge é questão de alterar o TOML;
  nenhuma etapa manual extra é necessária.

---

## 📌 Próximos passos sugeridos

1. Expor métricas de merges (participantes por origem) diretamente na saída do
   CLI para facilitar auditoria.
2. Permitir que merges definam `media_dir` dedicado quando anexos forem comuns.
3. Acrescentar testes que cubram `tag_style = prefix/brackets` e validação de
   `group_emojis` ausentes.

Com isso, a documentação acompanha o comportamento real do código e substitui o
plano antigo por uma visão operacional do recurso de grupos virtuais.
