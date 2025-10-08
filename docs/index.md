<div class="hero-banner">
  <h1>Egrégora Reports</h1>
  <p>
    Relatórios diários, semanais e mensais gerados automaticamente a partir das
    conversas do WhatsApp, com anonimização completa, contexto enriquecido e
    histórico pesquisável.
  </p>
  <div class="hero-actions">
    <a class="primary" href="reports/daily/index.md">
      <span class="twemoji">📅</span>
      Ver relatórios diários
    </a>
    <a class="secondary" href="docs/embeddings.md">
      <span class="twemoji">🧠</span>
      Entender RAG & embeddings
    </a>
  </div>
</div>

## O que você encontra aqui

<div class="card-grid">
  <div class="feature-card">
    <h3>📈 Relatórios automatizados</h3>
    <p>
      Gere newsletters diárias, semanais e mensais com um comando,
      reutilizando histórico e enriquecimento de links.
    </p>
  </div>
  <div class="feature-card">
    <h3>🛡️ Privacidade garantida</h3>
    <p>
      Anonimização determinística, filtros de sistema e revisão opcional
      asseguram que nenhum dado sensível chegue ao HTML final.
    </p>
  </div>
  <div class="feature-card">
    <h3>🔎 Busca semântica</h3>
    <p>
      Habilite o módulo de RAG com embeddings do Gemini para consultar o
      histórico com rapidez e precisão.
    </p>
  </div>
</div>

## Comece por aqui

<div class="quick-links">
  <a href="README.md">🚀 Configuração do pipeline</a>
  <a href="backlog_processing.md">🗂️ Processar backlog de zips</a>
  <a href="discover.md">🔍 Calcular identificadores anônimos</a>
  <a href="privacy.md">🛡️ Entenda o sistema de privacidade</a>
</div>

::: tip
Caso esteja adicionando um novo grupo, lembre-se de rodar
`python tools/build_reports.py` depois de gerar as newsletters para publicar os
arquivos em `docs/reports/`.
:::
