# Plano de Implementação: Privacidade Simples e Determinística

## 📋 Visão Geral

A privacidade no Egregora agora se apoia em duas camadas automáticas. O objetivo
é minimizar a complexidade técnica e confiar na robustez dos modelos modernos de
linguagem para seguir instruções claras.

1. **Anonimização determinística** (Camada 1)
2. **Instruções explícitas ao LLM** (Camada 2)

---

## 🧭 Novo Fluxo

```
WhatsApp ZIP → [Anonimização de autores] → Prompt com instruções de privacidade → Newsletter
```

- Telefones e apelidos são convertidos em pseudônimos determinísticos (`User-XXXX`)
  antes de qualquer processamento.
- O prompt enviado ao Gemini reforça que a newsletter **não deve** expor nomes,
  telefones ou contatos diretos.
- Para newsletters sensíveis, mantenha uma revisão humana antes do envio.

Esse arranjo cobre 80–90% das necessidades de privacidade sem depender de
heurísticas frágeis, listas manuais de nomes ou regex complexas.

---

## 🎯 Objetivos Atualizados

1. **Privacidade determinística**: nenhuma mensagem cruza o pipeline com autores
   reais.
2. **Menos código, menos riscos**: nenhuma camada de regex ou heurística precisa
   ser mantida.
3. **Transparência para quem participa**: qualquer pessoa pode descobrir o seu
   identificador anônimo localmente.

---

## 🧩 Componentes Principais

### `src/egregora/anonymizer.py`

- Implementa `Anonymizer`, responsável por normalizar telefones ou apelidos e
  gerar UUIDv5 determinísticos com o formato legível `User-XXXX`/`Member-XXXX`.
- É usado tanto no pipeline principal quanto na ferramenta de descoberta.

### `src/egregora/pipeline.py`

- Aplica a anonimização linha a linha usando uma regex leve apenas para detectar
  o autor do transcript.
- O prompt principal já contém instruções rígidas de privacidade.

### `src/egregora/__main__.py`

- Mantém as flags de anonimização para depuração local.

### `docs/discover.md`

- Continua ensinando como qualquer pessoa pode calcular o próprio identificador
  anônimo usando a CLI ou exemplos na documentação.

---

## 🧪 Testes

- `tests/test_anonymizer.py` cobre normalização e geração de pseudônimos.
- `tests/test_privacy_e2e.py` garante que os autores são anonimizados e que a
  configuração pode desativar a etapa quando desejado.

---

## ✅ Benefícios do Novo Desenho

- **Menos manutenção**: não existe mais um conjunto de regex frágeis para
  telefones, nomes ou frases específicas.
- **Mais confiança**: o comportamento depende de instruções claras ao LLM,
  alinhado com as capacidades atuais de modelos como o Gemini 2.0.
- **Flexibilidade**: equipes que precisam de uma camada extra podem manter uma
  revisão humana antes da publicação.
- **Clareza para usuários**: a documentação reflete exatamente o que o sistema
  faz — nada oculto, nada mágico.

---

## 🚀 Próximos Passos

1. Monitorar execuções reais para validar a taxa de falso-positivo/negativo da
   etapa automatizada.
2. Ajustar as instruções do prompt conforme feedback.
3. Documentar recomendações de revisão humana (checklist simples) para casos em
   que a newsletter trate de temas muito sensíveis.

Com essas mudanças, o Egregora mantém a privacidade como prioridade sem carregar
complexidade desnecessária.
