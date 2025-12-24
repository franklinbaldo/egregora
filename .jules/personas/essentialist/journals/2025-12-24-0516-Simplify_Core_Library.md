## 💎 2025-12-24-0527 - Simplifying the Core Library
**Observation:** The 'core' library in 'src/egregora_v3/core' contained several violations of the Essentialist Heuristics. The 'Document.create' method in 'types.py' had convoluted, implicit logic for ID generation and used a 'smart default'. The configuration loader in 'config.py' had a subtle bug where environment variables were incorrectly ignored when a TOML file was present.

**Action:** I refactored the 'core' library to address these issues.
- In 'types.py', I refactored the 'Document.create' method to require an explicit 'id', establishing a single, clear path for identity (**One good path over many flexible paths**). I also removed the 'untitled' smart default for slugs (**Simple defaults over smart defaults**). This was a successful simplification.
- In 'config.py', I fixed the configuration precedence bug to ensure that environment variables correctly override the TOML file. While the final implementation is more complex than ideal, it is explicit and correct. I added a '# FIXME' to acknowledge this technical debt.
- I used a Test-Driven Development approach for all changes, adding a regression test for the config bug and updating all tests affected by the refactoring of 'Document.create'.
