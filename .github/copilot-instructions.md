# Copilot Code Review Instructions

This repository uses `AGENTS.md`, `.kiro/steering/`, `.kiro/specs/`, and supporting `docs/` as the source of truth for agentic SDLC and spec-driven development.

When reviewing pull requests, focus on whether the change follows the repository workflow and project memory:

- Check consistency with `AGENTS.md`.
- Check consistency with `.kiro/steering/`, especially `product.md`, `tech.md`, `structure.md`, and `roadmap.md`.
- Check consistency with active specs under `.kiro/specs/` when the PR is spec-related.
- When the PR implements or changes planned behavior, also check relevant reference docs under `docs/`, especially requirements and project-structure documents.

Review priorities:

1. Functional correctness and regressions
2. Consistency between requirements, design, tasks, implementation, and current spec phase
3. Privacy and data-sovereignty risks
4. Security issues, especially secret handling, unsafe file access, injection risks, and unintended external data transmission
5. Docker/network/configuration correctness
6. Directory responsibility and dependency-boundary violations
7. Missing or insufficient tests, smoke checks, or validation steps for changed behavior
8. Data loss, breaking changes, or migration risks

Repository-specific review guidance:

- Preserve the local-first, self-hosted architecture. Do not introduce cloud LLM inference or unnecessary external services.
- Keep external outbound communication limited to the approved services documented in steering: SearXNG search providers, SerpAPI, and Instagram Graph API.
- Ensure API keys and secrets stay in `.env` or documented secret stores and are never committed.
- Ensure user-visible notice exists when image URLs or uploaded image-derived data are sent to external APIs.
- Respect the architecture flow: Open WebUI → Pipeline → Dify Workflow → backend services.
- Respect directory responsibilities:
  - `docker/` is for infrastructure definitions.
  - `pipelines/` is for Open WebUI Python extensions.
  - `workflows/` is for Dify workflow exports.
  - `comfyui-workflows/` is for ComfyUI API Format workflows.
  - `scripts/` is for idempotent operational scripts.
  - `tests/` is for integration and smoke tests.
- Watch shared seams carefully:
  - `pipelines/dify_bridge.py`
  - `imgpush` integration
  - `workflows/` input/output formats
  - Docker network and service-name changes
- Respect spec dependency order from `.kiro/steering/roadmap.md`. Changes to shared foundation specs such as `infrastructure` or `dify-integration` may affect downstream feature specs.

Do not comment on minor style issues unless they affect maintainability, correctness, security, privacy, or repository conventions.

Prefer concise, actionable comments.
When suggesting a fix, explain the risk and the smallest safe change.