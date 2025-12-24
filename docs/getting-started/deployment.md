# Deploying Your Blog

Egregora generates a standard static site compatible with any hosting provider.

## GitHub Pages (Recommended)

Egregora includes a pre-configured GitHub Actions workflow for zero-config deployment.

### 1. Push to GitHub

Initialize a git repository and push your site:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main
```

### 2. Configure Settings

1. Go to your repository **Settings** → **Pages**.
2. Under **Build and deployment**, select **GitHub Actions** as the source.
3. (Optional) If you don't see the workflow, ensure `.github/workflows/docs-pages.yml` exists in your repo.

### 3. Verify

On every push to `main`, GitHub Actions will:

1. Install Egregora
2. Build your site
3. Deploy to `https://USERNAME.github.io/REPO/`

## Manual Deployment

You can also deploy manually using the `mkdocs` CLI:

```bash
uv run mkdocs gh-deploy
```

This will build the site and push it to the `gh-pages` branch.

!!! warning "Known Issues"
    Manual deployment bypasses the automated build steps (like generating the demo site or enriching content in CI). We recommend using the GitHub Actions workflow.

## Other Hosting Providers

Since Egregora outputs static HTML, you can host it anywhere:

- **Netlify**: Drag and drop the `site/` folder (after running `mkdocs build`).
- **Vercel**: Import your Git repo and set the build command to `uv run mkdocs build` and output directory to `site`.
- **Cloudflare Pages**: Use build command `uv run mkdocs build` and output directory `site`.

## Custom Domain

To handle a custom domain (e.g., `blog.example.com`):

1. Update `site_url` in `mkdocs.yml`.
2. Add a `CNAME` file to `docs/CNAME` with your domain name.
3. Update your DNS provider settings.
