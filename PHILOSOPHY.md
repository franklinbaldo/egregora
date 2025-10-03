# Egregora — Manual Essencial

Egregora é um projeto comunitário que transforma exports de grupos do WhatsApp em newsletters diárias. Este documento descreve os
princípios que orientam as decisões de produto, sem repetir o conteúdo dos guias técnicos.

## 1. Visão e valores

- **Propósito**: preservar a inteligência coletiva de grupos em um formato navegável e compartilhável.
- **Transparência**: links apontam para a mensagem original e contextos difíceis são apresentados como surgiram.
- **Respeito**: anonimização determinística protege identidades sem apagar autoria.
- **Enxugue o acoplamento**: preferimos fluxos pequenos e auditáveis a arquiteturas distribuídas complexas.

## 2. Pilares do produto

### Enriquecimento automático
O módulo de enriquecimento lê URLs e marcadores de mídia com o suporte nativo do Gemini (`Part.from_uri`). Ele resume, classifica
e calcula relevância antes de o prompt principal ser montado. O cache persistente evita custos repetidos.

### Busca com RAG
O histórico de newsletters fica indexado para consulta rápida. O modo padrão usa TF-IDF, e é possível ativar embeddings do Gemini
para buscas semânticas quando a API estiver disponível. O servidor MCP expõe o RAG para Claude e outros clientes.

### Privacidade por padrão
Identificadores pessoais são substituídos antes de qualquer chamada ao LLM. Os prompts reforçam que o modelo não deve revelar
dados sensíveis, e há ferramentas para que cada participante calcule o próprio pseudônimo.

## 3. Decisões orientadoras

1. **Apoie-se no Gemini**: evitar bibliotecas de parsing adicionais enquanto o suporte nativo der conta (PDFs, YouTube, imagens).
2. **Priorize caches**: todo processamento caro deve escrever em disco para reduzir custos futuros.
3. **Fallback seguro**: sempre forneça um caminho operacional mesmo sem enriquecimento ou embeddings habilitados.
4. **MCP como fronteira**: integrações externas conversam com o servidor MCP, mantendo o núcleo do RAG independente.

## 4. Como colaborar

- Comece pelo `README.md` e pelo `ENRICHMENT_QUICKSTART.md` para entender o fluxo operacional.
- Ao propor mudanças, descreva o impacto em privacidade, custo e velocidade.
- Prefira pull requests pequenos acompanhados de notas sobre testes manuais ou automatizados.
- Atualize a documentação relevante ao alterar comportamento visível para usuários ou integradores.

## 5. Para aprofundar

- `README.md` — visão geral e comandos principais.
- `CONTENT_ENRICHMENT_DESIGN.md` — arquitetura detalhada do módulo de enriquecimento.
- `docs/mcp-rag.md` — funcionamento do servidor MCP e ferramentas disponíveis.
- `docs/embeddings.md` — como habilitar e operar o modo semântico.
- `MIGRATION_GUIDE.md` — diferenças entre versões e passos recomendados.

---

_Egregora é um experimento contínuo em curadoria coletiva. Use, adapte e compartilhe melhorias._
