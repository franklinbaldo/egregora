# Egregora

Automação para gerar newsletters diárias a partir de exports do WhatsApp usando o Google Gemini. Agora inclui um sistema opcional de **enriquecimento de conteúdos compartilhados**, capaz de resumir e contextualizar links citados nas conversas antes de gerar a newsletter.

## 🌟 Principais recursos

- **Pipeline completo** para transformar arquivos `.zip` do WhatsApp em newsletters Markdown.
- **Integração com Gemini**: usa `google-genai` com configuração de segurança ajustada para conteúdos de grupos reais.
- **Enriquecimento de links**: identifica URLs e mídias e usa o suporte nativo do Gemini a `Part.from_uri` para analisá-los em paralelo com um modelo dedicado.
- **Configuração flexível**: diretórios, fuso horário, modelos e limites podem ser ajustados via CLI ou API.
- **Documentação extensa**: consulte `ENRICHMENT_QUICKSTART.md`, `INTEGRATION_GUIDE.md` e `CONTENT_ENRICHMENT_DESIGN.md` para aprofundar.

## 📦 Requisitos

- [Python](https://www.python.org/) 3.10 ou superior
- [uv](https://docs.astral.sh/uv/) para gerenciar dependências
- Variável `GEMINI_API_KEY` configurada com uma chave válida da API do Gemini

Dependências principais:

- `google-genai`

## 🚀 Instalação

1. Instale o `uv` (caso ainda não tenha):

   ```bash
   pip install uv
   ```

2. Sincronize as dependências do projeto:

   ```bash
   uv sync
   ```

3. Verifique se a variável `GEMINI_API_KEY` está presente no ambiente:

   ```bash
   export GEMINI_API_KEY="sua-chave"
   ```

## 🧠 Enriquecimento de conteúdos

O novo módulo de enriquecimento executa três etapas:

1. **Extração** – percorre os transcritos procurando URLs e marcadores de mídia (`<Mídia oculta>`), capturando até 3 mensagens de contexto antes/depois.
2. **Análise com Gemini** – envia cada referência para um modelo configurável que lê a URL diretamente e devolve resumo, pontos-chave, tom e relevância (1–5).
3. **Filtragem** – somente itens com relevância acima do limiar configurado entram no prompt final.

### Configuração rápida

```bash
uv run egregora --days 1 --relevance-threshold 3 --max-enrichment-items 20
```

Parâmetros úteis:

- `--enable-enrichment` / `--disable-enrichment`
- `--relevance-threshold` (1–5)
- `--max-enrichment-items`
- `--max-enrichment-time`
- `--enrichment-model`
- `--enrichment-context-window`
- `--analysis-concurrency`

Consulte `ENRICHMENT_QUICKSTART.md` para ver exemplos de execução e melhores práticas.

## 🧭 Estrutura padrão

- `data/whatsapp_zips/`: arquivos `.zip` exportados do WhatsApp com a data no nome (`YYYY-MM-DD`).
- `newsletters/`: destino das newsletters geradas (`YYYY-MM-DD.md`).

As pastas são criadas automaticamente na primeira execução.

## 🛠️ Uso via CLI

```bash
uv run egregora \
  --zips-dir data/whatsapp_zips \
  --newsletters-dir newsletters \
  --group-name "RC LatAm" \
  --model gemini-flash-lite-latest \
  --days 2
```

Adicione as flags de enriquecimento conforme necessário. O CLI informa ao final quantos links foram processados e quantos atingiram o limiar de relevância.

## 🧪 Testes manuais

- Rode `python example_enrichment.py` para validar rapidamente o módulo de enriquecimento (define `GEMINI_API_KEY` antes para executar a análise com o LLM).
- Execute o comando principal com `--days 1` usando um exporto pequeno para validar o fluxo completo.

## 📚 Documentação complementar

- `ENRICHMENT_QUICKSTART.md` – visão geral + primeiros passos.
- `INTEGRATION_GUIDE.md` – alterações necessárias para integrar ao pipeline.
- `CONTENT_ENRICHMENT_DESIGN.md` – arquitetura completa, decisões e roadmap.
- `README_IMPROVED.md` – versão expandida do README com contexto filosófico do projeto.

## 🤝 Contribuição

1. Faça fork do repositório e crie um branch.
2. Instale as dependências com `uv sync`.
3. Adicione testes ou atualize os exemplos conforme necessário.
4. Abra um PR descrevendo claramente as alterações.

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).
