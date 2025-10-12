# Summary of Remaining Open Issues

This document provides a high-level summary of the remaining open issues in the `dev/issues` directory.

## High Priority

*   **Architecture Separation (`architecture-separation.md`):** The generator system, generated content, and data storage are all in a single repository, leading to a number of problems. The proposed solution is to separate them into three distinct repositories.
*   **CLI-Only Usage (`cli-only-usage.md`):** The CLI experience can be improved by adding more flags, a setup wizard, and better documentation for TOML-free usage.
*   **Configuration UX (`configuration-ux.md`):** The configuration process is cumbersome and error-prone. A configuration wizard, better error messages, and a minimal default configuration are proposed.
*   **Error Messages & Debugging (`error-messages-debugging.md`):** Error messages are often unhelpful. A user-friendly error handler, layered error information, and better warning management are proposed.
*   **Privacy & Security (`privacy-security.md`):** The current privacy features are basic. Configurable privacy levels, PII detection, data retention policies, and a privacy audit trail are proposed.
*   **Offline/Demo Mode (`offline-demo-mode.md`):** The pipeline fails without a valid API key. A demo mode that uses mock data is proposed.

## Medium Priority

*   **Dependency Management (`dependency-management.md`):** The project has outdated and deprecated dependencies. The proposed solution is to update dependencies and improve the handling of optional dependencies.
*   **Media Handling (`media-handling.md`):** Media handling is basic. The proposed solution is to add features like optimization, validation, and better organization.
*   **Performance & Scalability (`performance-scalability.md`):** The pipeline has performance and scalability issues. Progress indicators, streaming processing, and parallelization are proposed.
*   **Testing & Development (`testing-development.md`):** The testing infrastructure can be improved. Better AI mocking, test data generation, performance testing, and a more streamlined development environment are proposed.

## Low Priority

*   **Output Formats (`output-formats.md`):** The pipeline only outputs Markdown. Support for multiple output formats, such as HTML, JSON, and PDF, is proposed.
