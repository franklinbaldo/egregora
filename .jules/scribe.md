# Scribe's Journal

## 2025-05-15 - Missing Plugins & Broken Links
**Confusion:** The README instructed users to run a preview command that failed because it was missing the required `mkdocs-blogging-plugin`. It also pointed to a configuration file path that didn't exist (`docs/configuration.md`), leading to a 404.
**Discovery:** The actual configuration documentation lives at `docs/getting-started/configuration.md`. The `mkdocs-blogging-plugin` is a mandatory dependency for the site build process as per project memory.
**Resolution:** Updated `README.md` to include the missing plugin in the `uvx` command and corrected the link to the configuration guide.

## 2025-05-15 - Protocol Drift & Broken Links
**Confusion:** `docs/architecture/protocols.md` referenced the legacy `OutputAdapter` as a protocol and pointed to non-existent API docs.
**Discovery:** The actual protocol is `OutputSink` in `src/egregora/data_primitives/protocols.py`, and `InputAdapter` is an ABC in `src/egregora/input_adapters/base.py`.
**Resolution:** Updated `docs/architecture/protocols.md` to match the codebase and removed dead links.
