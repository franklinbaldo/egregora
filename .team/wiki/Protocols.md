# 🚦 Protocols & Workflows

Standard Operating Procedures (SOPs) for the JULES Team.

## 🔄 Session Management

### Start of Session
1.  **Authentication:** `my-tools login` with specific goals.
2.  **Situation Awareness:** Check email, roster, and task lists.
3.  **Branching:** Always target the `jules` branch.

### End of Session
1.  **Communication:** Email relevant personas about findings.
2.  **Journaling:** Create a journal entry (Observation/Action/Reflection).
3.  **Submission:** Run pre-commit checks and submit a PR.

## 🧪 Behavior-Driven Development (BDD)

All features must follow the **Given-When-Then** cycle.
1.  **Specify:** Write the behavior in Gherkin format.
2.  **Implement:** Write the code to satisfy the spec.
3.  **Verify:** Run tests to confirm the behavior.

## 📝 Commit Standards

- **Format:** `[emoji] type: description` (e.g., `📚 lore: update wiki`).
- **Scope:** One logical change per commit.
- **Verification:** Changes must be verified via `read_file` or tests before committing.

## 🛡️ Security Protocols

- **Secrets:** Never commit API keys or credentials. Use environment variables.
- **Dependencies:** Verify package integrity before installing.
- **Privacy:** Adhere to the [Privacy-First Mandate](Privacy.md).
