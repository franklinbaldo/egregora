# Egregora

Automação para gerar newsletters diárias a partir de exports do WhatsApp usando Google Gemini.

## Requisitos

- [Python](https://www.python.org/) 3.10 ou superior
- [uv](https://docs.astral.sh/uv/) (gerenciador de dependências da Astral)
- Variável de ambiente `GEMINI_API_KEY` com uma chave válida da API do Gemini

## Instalação

1. Instale o uv caso ainda não tenha:

   ```bash
   pip install uv
   ```

2. Sincronize as dependências do projeto:

   ```bash
   uv sync
   ```

## Estrutura de pastas

Por padrão, o pipeline espera:

- `data/whatsapp_zips/`: arquivos `.zip` diários exportados do WhatsApp, cada um contendo um ou mais `.txt` e com a data no nome (`YYYY-MM-DD`).
- `newsletters/`: pasta onde as newsletters geradas serão salvas como `YYYY-MM-DD.md`.

As pastas são criadas automaticamente na primeira execução caso ainda não existam.

## Uso

Execute o pipeline via uv:

```bash
uv run egregora \
  --zips-dir data/whatsapp_zips \
  --newsletters-dir newsletters \
  --group-name "RC LatAm" \
  --model gemini-flash-lite-latest \
  --days 2
```

Todos os parâmetros são opcionais; se omitidos, os valores padrão acima são usados. O fuso horário padrão é `America/Porto_Velho`. Use `--timezone` para fornecer outro identificador IANA.

Durante a execução, os dois arquivos `.zip` mais recentes são lidos (ou a quantidade especificada em `--days`). Caso exista uma newsletter do dia anterior, ela é carregada como contexto adicional para a LLM. O conteúdo gerado é salvo em `newsletters/{DATA}.md`, onde `{DATA}` é a data mais recente encontrada entre os arquivos processados.

## Desenvolvimento

- O código principal está em `src/egregora`.
- O entrypoint de linha de comando está em `egregora.__main__`.
- Adicione novas dependências com `uv add <pacote>`.

## Licença

Veja o arquivo [LICENSE](LICENSE).
