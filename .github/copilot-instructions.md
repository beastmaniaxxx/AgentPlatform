\# Copilot Code Review Instructions

This repository uses AGENTS.md and `.kiro/steering/` as the long-lived source of truth for agentic SDLC and spec-driven development.

When reviewing pull requests, focus on whether the change follows the repository workflow and project memory:

\- Check consistency with `AGENTS.md`.
\- Check consistency with `.kiro/steering/` when the change affects architecture, naming, security constraints, tech stack decisions, or API standards.
\- Check whether implementation matches active specs under `.kiro/specs/` when the PR is spec-related.

Review priorities:

1. Functional correctness and regressions
2. Security issues, especially authorization, secret handling, unsafe file access, and injection risks
3. Data loss or breaking changes
4. Missing or insufficient tests for changed behavior
5. Violations of architecture, API, naming, or project structure rules
6. Inconsistency between requirements, design, tasks, and implementation


Do not comment on minor style issues unless they affect maintainability or correctness.

Prefer concise, actionable comments.
When suggesting a fix, explain the risk and the smallest safe change.