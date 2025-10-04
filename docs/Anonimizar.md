# Plano de Implementação: Privacidade Simples e Determinística

## 📋 Visão Geral

A privacidade no Egregora agora se apoia em duas camadas automáticas e uma etapa
opcional de revisão. O objetivo é minimizar a complexidade técnica e confiar na
robustez dos modelos modernos de linguagem para seguir instruções claras.

1. **Anonimização determinística** (Camada 1)
2. **Instruções explícitas ao LLM** (Camada 2)
3. **Revisão opcional** via segunda chamada ao LLM ou validação humana

---

## 🧭 Novo Fluxo

```
WhatsApp ZIP → [Anonimização de autores] → Prompt com instruções de privacidade → Newsletter
                                                      ↘ (opcional) Revisão automática ↗
```

- Telefones e apelidos são convertidos em pseudônimos determinísticos (`User-XXXX`)
  antes de qualquer processamento.
- O prompt enviado ao Gemini reforça que a newsletter **não deve** expor nomes,
  telefones ou contatos diretos.
- Quando necessário, o pipeline pode fazer uma segunda chamada ao LLM com um
  prompt simples de revisão ou encaminhar para revisão humana.

Esse arranjo cobre 80–90% das necessidades de privacidade sem depender de
heurísticas frágeis, listas manuais de nomes ou regex complexas.

---

## 🎯 Objetivos Atualizados

1. **Privacidade determinística**: nenhuma mensagem cruza o pipeline com autores
   reais.
2. **Menos código, menos riscos**: nenhuma camada de regex ou heurística precisa
   ser mantida.
3. **Revisão quando necessário**: se o time quiser uma verificação adicional,
   basta ligar o modo de segunda passagem.
4. **Transparência para quem participa**: qualquer pessoa pode descobrir o seu
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
- Quando `PrivacyConfig.double_check_newsletter` está habilitado, uma segunda
  chamada ao Gemini revisa a newsletter para remover traços residuais de PII.

### `src/egregora/config.py`

- Define `PrivacyConfig` com dois campos:
  - `double_check_newsletter`: ativa/desativa a segunda passagem automática.
  - `review_model`: permite escolher um modelo diferente para a revisão
    (por padrão reutiliza o mesmo modelo da geração).

### `src/egregora/__main__.py`

- Mantém as flags de anonimização e adiciona:
  - `--double-check-newsletter`
  - `--review-model`
- Removeu opções relacionadas a regex ou filtros heurísticos.

### `docs/discover.md`

- Continua ensinando como qualquer pessoa pode calcular o próprio identificador
  anônimo usando a CLI ou exemplos na documentação.

---

## 🔁 Fluxo de Revisão Opcional

Quando a flag `--double-check-newsletter` está ativa, o pipeline executa:

```python
revised = _run_privacy_review(
    client,
    model=config.privacy.review_model or config.model,
    newsletter_text=newsletter_text,
)
```

O prompt de revisão solicita explicitamente que o modelo remova nomes próprios,
telefones, e-mails e endereços. Caso nada precise ser alterado, o modelo deve
retornar o texto original, mantendo o processo determinístico.

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
- **Flexibilidade**: equipes que precisam de uma camada extra podem habilitar a
  revisão automática ou recorrer a revisão humana.
- **Clareza para usuários**: a documentação reflete exatamente o que o sistema
  faz — nada oculto, nada mágico.

---

## 🚀 Próximos Passos

1. Monitorar execuções reais para validar a taxa de falso-positivo/negativo da
   revisão automática.
2. Ajustar a instrução de revisão conforme feedback.
3. Documentar recomendações de revisão humana (checklist simples) para casos em
   que a newsletter trate de temas muito sensíveis.

Com essas mudanças, o Egregora mantém a privacidade como prioridade sem carregar
complexidade desnecessária.
