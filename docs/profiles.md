# Perfis Analíticos dos Participantes

O Egregora pode gerar perfis incrementais para cada membro dos grupos processados.
Após cada newsletter diária, o pipeline analisa a participação de cada integrante
(até onde a anonimização permite) e decide se vale reescrever o perfil.

## Estrutura de diretórios

- `data/profiles/<uuid>.json` – dados estruturados, ideais para uso posterior ou
  integrações.
- `docs/profiles/<uuid>.md` – versão em Markdown exposta pelo MkDocs. O arquivo
  `docs/profiles/index.md` é reescrito automaticamente com uma lista atualizada
  de todos os perfis disponíveis.

Os identificadores de arquivo utilizam UUID v5 determinísticos a partir do
telefone ou apelido original (antes da anonimização).

## Configuração

```toml
[profiles]
enabled = true
profiles_dir = "data/profiles"
profiles_docs_dir = "docs/profiles"
min_messages = 2
min_words_per_message = 15
decision_model = "gemini-2.0-flash-exp"
rewrite_model = "gemini-2.0-flash-exp"
```

- `enabled`: habilita/desabilita o módulo (por padrão já vem ativo).
- `min_messages` / `min_words_per_message`: limites mínimos para considerar uma
  participação relevante no dia.
- `decision_model` / `rewrite_model`: modelos Gemini usados para decidir pela
  atualização e reescrever o perfil.

⚠️ É necessário ter `GEMINI_API_KEY` (ou `GOOGLE_API_KEY`) configurado. Caso a
chave não esteja presente, as atualizações de perfis são ignoradas.

## Fluxo de atualização

1. Depois de gerar a newsletter do dia, o pipeline analisa as mensagens originais
   (não anonimizadas) para identificar quem participou e com qual intensidade.
2. O `ProfileUpdater` decide se merece uma atualização (chamando o modelo de
   decisão) e, em caso afirmativo, reescreve o perfil completo com base nas
   conversas mais recentes.
3. O repositório persiste o resultado em JSON + Markdown e atualiza o índice.

Os perfis publicados podem ser versionados, enviados como artefatos do GitHub
Actions ou arquivados em serviços externos (Internet Archive, por exemplo).
