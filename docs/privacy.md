# 🛡️ Sistema de Privacidade

O Egregora segue uma abordagem enxuta para proteger informações pessoais. O
processo combina anonimização determinística com instruções claras ao modelo de
linguagem, reduzindo a chance de informações sensíveis aparecerem no resultado.

## 1. Anonimização determinística

- Telefones e apelidos são convertidos em identificadores como `Member-ABCD`
  usando UUIDv5.
- Nenhum mapeamento é persistido; o algoritmo é puro e repetível.
- O formato `User-ABCD`/`Member-EFGH` é o padrão fixo para garantir leitura
  simples e consistência.
- A flag `--disable-anonymization` desativa esta etapa para depuração local.

## 2. Instruções explícitas ao LLM

- O prompt do Gemini instrui o modelo a **não mencionar nomes próprios, números
  de telefone ou contatos diretos**.
- Mensagens que mencionam dados pessoais continuam no transcript, mas são
  processadas pelo LLM com esse contexto claro.
- A efetividade típica observada com modelos modernos (como Gemini 2.0) fica na
  casa de 80–90% sem nenhuma filtragem adicional.

## Revisão recomendada

- Para newsletters sensíveis, mantenha uma leitura humana antes do envio.
- Ajuste o prompt principal conforme necessário para reforçar políticas internas.

## Autodescoberta segura

Cada pessoa pode descobrir o próprio identificador anônimo executando:

```bash
uv run egregora discover "<telefone ou apelido>"
```

Consulte [🔍 Autodescoberta de Identificadores Anônimos](discover.md) para ver
exemplos e fluxos sugeridos.

## Configuração rápida

```python
from egregora.config import PipelineConfig

config = PipelineConfig.with_defaults()
config.privacy.double_check_newsletter = True
config.privacy.review_model = "gemini-1.5-flash"
config.anonymization.output_format = "short"
```

Essas opções afetam tanto a execução via CLI quanto o uso como biblioteca.
