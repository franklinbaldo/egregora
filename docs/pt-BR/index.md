<div class="hero-banner">
  <h1>Relatórios atualizados diariamente</h1>
  <p>
    Acompanhe o resumo das conversas e links compartilhados no seu grupo. Cada
    relatório é gerado automaticamente com anonimização, enriquecimento de
    conteúdo e histórico pesquisável.
  </p>
  <div class="hero-actions">
    <!-- LATEST_DAILY_BUTTON -->
                        <a class="primary" href="#">
      <span class="twemoji">🆕</span>
      Nenhum relatório disponível
    </a>
    <!-- /LATEST_DAILY_BUTTON -->
  </div>
</div>

## Últimos relatórios diários

<!-- LATEST_DAILY_CONTENT -->
<p>Nenhum relatório publicado ainda.</p>
<!-- /LATEST_DAILY_CONTENT -->

## Documentação do pipeline

<div class="quick-links">
  <a href="{{ 'quickstart.md' | url }}">🚀 Guia rápido de execução</a>
  <a href="{{ 'backlog_processing.md' | url }}">🗂️ Processamento de backlog</a>
  <a href="{{ 'discover.md' | url }}">🔍 Identificadores anônimos</a>
  <a href="{{ 'privacy.md' | url }}">🛡️ Sistema de privacidade</a>
  <a href="{{ 'embeddings.md' | url }}">🧠 Embeddings & RAG</a>
</div>

::: tip
Após gerar novas newsletters, execute `python tools/build_reports.py` para
atualizar os relatórios publicados antes de fazer o deploy.
:::