# 🛡️ Sistema de Privacidade

O Egregora segue uma abordagem enxuta para proteger informações pessoais. O
processo prioriza anonimização determinística e instruções claras ao modelo de
linguagem, recorrendo a uma segunda revisão apenas quando necessário.

## 1. Anonimização determinística

- Telefones e apelidos são convertidos em identificadores como `User-ABCD` ou
  `Member-EFGH` usando UUIDv5.
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

## Revisão opcional

- Quando necessário, habilite `--double-check-newsletter` para executar uma
  segunda chamada ao LLM revisando a newsletter gerada.
- O prompt de revisão pede para remover números de telefone, e-mails, nomes
  próprios e endereços físicos, devolvendo exatamente o mesmo texto quando nada
  precisa ser alterado.
- Também é possível manter uma revisão humana como etapa final para newsletters
  extremamente sensíveis.

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
```

Essas opções afetam tanto a execução via CLI quanto o uso como biblioteca.
