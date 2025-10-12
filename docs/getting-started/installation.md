# Instalação

## Requisitos

- Python 3.11 ou superior
- [uv](https://docs.astral.sh/uv/) (gerenciador de dependências)
- Chave de API do Google Gemini

## Instalar uv

=== "macOS/Linux"
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"
    ```powershell
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "pip"
    ```bash
    pip install uv
    ```

## Clonar Repositório

```bash
git clone https://github.com/yourorg/egregora.git
cd egregora
```

## Instalar Dependências

```bash
# Instalar core + RAG + Profiles
uv sync

# Instalar com documentação
uv sync --extra docs

# Instalar com ferramentas de desenvolvimento
uv sync --extra lint --extra test
```

## Configurar API Key

=== "Bash/Zsh"
    ```bash
    export GEMINI_API_KEY="your-api-key-here"
    ```

=== "Fish"
    ```fish
    set -x GEMINI_API_KEY "your-api-key-here"
    ```

=== "PowerShell"
    ```powershell
    $env:GEMINI_API_KEY="your-api-key-here"
    ```

=== "Arquivo .env"
    ```bash
    # Criar arquivo .env
    echo "GEMINI_API_KEY=your-api-key-here" > .env

    # Carregar no shell
    source .env  # ou: set -a; source .env; set +a
    ```

!!! tip "Obtendo API Key"
    Obtenha sua chave gratuita em [Google AI Studio](https://makersuite.google.com/app/apikey)

## Verificar Instalação

```bash
# Verificar versão
uv run egregora --version

# Testar CLI
uv run egregora --help
```

Você deverá ver a ajuda do CLI sem erros.

## Próximo Passo

Agora você está pronto para [gerar seu primeiro post](first-post.md)!
