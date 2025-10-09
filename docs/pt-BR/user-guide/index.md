# Quickstart (5 minutos)

## 1) Instalar

```bash
uv sync
```

## 2) Preparar export do WhatsApp

Exporte o grupo sem mídia (ZIP).
Coloque em `data/whatsapp_zips/`.

## 3) Rodar

```bash
uv run egregora --config egregora.toml --days 1
```

## 4) Ver os posts

Abra `site/` (ou GitHub Pages).
Veja Diários/Semanais/Mensais.

### Problemas comuns

- ZIP com nome fora do padrão → veja “FAQ: Nomeação de ZIP”.
- Falha de rede no enrichment → rode com `--disable-enrichment` e tente depois.
