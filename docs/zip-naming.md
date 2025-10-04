# WhatsApp ZIP Naming Guide

Este guia explica como nomear arquivos ZIP do WhatsApp para obter os melhores resultados com o Egregora.

## 📋 Resumo Executivo

**Boa notícia**: Você pode usar arquivos ZIP exatamente como o WhatsApp os exporta! O sistema detecta datas automaticamente. Renomear é opcional.

## ✅ Nomes Aceitos

### Automático (Recomendado)
```
✅ Conversa do WhatsApp com Meu Grupo.zip
✅ WhatsApp Chat with Team Name.zip  
✅ Chat de WhatsApp con Equipo.zip
✅ Conversa do WhatsApp com Grupo 🚀.zip
```

### Explícito (Controle Fino)
```
✅ 2025-10-03-Conversa do WhatsApp com Meu Grupo.zip
✅ 2025-09-15-Team Meeting Notes.zip
✅ 2024-12-25-Holiday Chat.zip
```

### Múltiplos Exports
```
✅ Conversa do WhatsApp com Team.zip           # Export de 2025-10-01
✅ 2025-10-03-Team.zip                         # Export de 2025-10-03  
✅ Conversa do WhatsApp com Team (1).zip       # Export adicional
```

## 🎯 Como Funciona a Detecção

O sistema tenta 3 métodos em ordem:

### 1. Nome do Arquivo (Prioridade Máxima)
```python
# Busca padrão YYYY-MM-DD no nome
"2025-10-03-Meu Grupo.zip" → 2025-10-03 ✅
```

### 2. Conteúdo das Mensagens
```python
# Analisa primeiras 20 linhas do chat
"[03/10/25 14:30:15] João: Olá!" → 2025-10-03 ✅
```

### 3. Data de Modificação (Fallback)
```python
# Usa timestamp do arquivo como último recurso
zip_path.stat().st_mtime → 2025-10-03 ⚠️
```

## ⚙️ Configuração do Sistema

### Detecção Automática Habilitada
O sistema **sempre** tenta detectar datas automaticamente. Não há configuração para desabilitar.

### Logs de Detecção
```bash
# Sucesso por nome
[DEBUG] Date from filename: 2025-10-03

# Sucesso por conteúdo  
[DEBUG] Date from content: 2025-10-03

# Fallback para mtime
[WARNING] ZIP 'Grupo.zip': Date extracted from file mtime (2025-10-03). 
Consider renaming to '2025-10-03-Grupo.zip' for explicit control.
```

## 🔄 Múltiplos Exports

### Como o Sistema Lida
1. **Agrupa por slug**: `meu-grupo` ← `Conversa do WhatsApp com Meu Grupo.zip`
2. **Ordena por data**: Export mais antigo → mais recente
3. **Mescla mensagens**: Deduplicação automática por timestamp + remetente

### Exemplo Prático
```
data/whatsapp_zips/
├── Conversa do WhatsApp com Team.zip         # 2025-09-01 a 2025-09-30
├── 2025-10-03-Team.zip                       # 2025-10-01 a 2025-10-03
└── Conversa do WhatsApp com Team (1).zip     # 2025-10-04 a 2025-10-04
```

**Resultado**: 3 exports mesclados em 1 grupo `team` com todas as mensagens ordenadas cronologicamente.

## 🛠️ Boas Práticas

### Para Uso Casual
- ✅ Use nomes naturais do WhatsApp
- ✅ Confie na detecção automática
- ✅ Verifique logs para confirmar data detectada

### Para Uso Avançado
- ✅ Use prefixo `YYYY-MM-DD-` para controle explícito
- ✅ Mantenha nomes descritivos após a data
- ✅ Agrupe exports relacionados com nomes similares

### Para Produção
- ✅ Sempre valide data detectada nos logs
- ✅ Use datas explícitas para exports críticos
- ✅ Mantenha backup dos ZIPs originais

## 🚨 Solução de Problemas

### Data Incorreta Detectada
```bash
# Problema: Data detectada errada
[WARNING] Detected future date 2026-01-01 - using file mtime instead

# Solução: Renomeie com data explícita
mv "Grupo.zip" "2025-10-03-Grupo.zip"
```

### Múltiplas Datas no Nome
```bash
# Problema: Nome ambíguo
"2024-12-25-backup-2025-01-01.zip"

# Sistema usa: 2024-12-25 (primeira ocorrência)
# Para forçar 2025-01-01, renomeie para:
"2025-01-01-backup-from-2024-12-25.zip"
```

### Exports Não Mesclados
```bash
# Problema: Grupos separados inesperadamente
"Team Meeting.zip" → slug: team-meeting
"Team-Meeting.zip" → slug: team-meeting  # Mesmo slug ✅
"Team_Meeting.zip" → slug: team-meeting  # Mesmo slug ✅

# Diferentes slugs (grupos separados):
"Team Meeting.zip" → team-meeting
"Team Reunion.zip" → team-reunion       # Grupos diferentes ❌
```

## 📊 Comandos Úteis

### Listar Grupos Descobertos
```bash
uv run egregora --list
# Mostra: slug, nome, quantidade de exports, período
```

### Modo Dry-Run
```bash
uv run egregora --dry-run
# Valida detecção sem processar
```

### Validar ZIP Específico
```bash
# Copie ZIP para diretório temporário e liste
mkdir temp && cp "Meu Grupo.zip" temp/
uv run egregora --zips-dir temp --list
```

## 🔮 Funcionalidades Futuras

### Em Desenvolvimento
- [ ] Extração de datas de nomes de mídia (`IMG-20251003-WA0001.jpg`)
- [ ] Suporte a mais formatos de data internacionais
- [ ] Validação de datas futuras
- [ ] Logs mais detalhados sobre estratégia de detecção

### Planejado
- [ ] Agrupamento inteligente de sufixos de browser `(1)`, `(2)`
- [ ] Detecção de intervalo de datas (primeira → última mensagem)
- [ ] Comando interativo de renomeação: `uv run egregora rename-zips`
- [ ] Cache de metadados para evitar re-análise

## 📚 Referências Técnicas

- **Implementação**: `src/egregora/group_discovery.py:_extract_date()`
- **Parsing de datas**: `src/egregora/date_utils.py`
- **Mesclagem**: `src/egregora/transcript.py:load_source_dataframe()`
- **Slugs**: `src/egregora/group_discovery.py:_slugify()`

## ❓ Perguntas Frequentes

### P: Posso misturar nomes explícitos e automáticos?
**R**: Sim! O sistema lida com ambos transparentemente.

### P: Como sei se a data foi detectada corretamente?
**R**: Verifique os logs. Nível WARNING indica fallback para mtime.

### P: Múltiplos exports do mesmo dia são permitidos?
**R**: Sim! São mesclados automaticamente por grupo.

### P: Emojis nos nomes são suportados?
**R**: Sim, mas são removidos na geração do slug.

### P: Posso usar subdiretorios em `whatsapp_zips/`?
**R**: Não, o sistema busca apenas na raiz do diretório especificado.