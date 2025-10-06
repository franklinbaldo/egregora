# Guia rápido do pipeline

1. **Configure o ambiente**
   ```bash
   uv sync --all-extras
   cp egregora.toml.example egregora.toml
   ```
2. **Adicione exports** em `data/whatsapp_zips/`.
3. **Rode o pipeline**
   ```bash
   uv run egregora --config egregora.toml process --days 2
   ```
4. **Gere os relatórios HTML**
   ```bash
   python tools/build_reports.py
   uv run --with mkdocs-material mkdocs build
   ```

Consulte o README na raiz do repositório para detalhes sobre anonimização,
perfis e integrações avançadas.
