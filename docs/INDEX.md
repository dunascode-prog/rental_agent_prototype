# Documentation Index

Source of truth: [Rental_Agent_Prototype_Architecture.pdf](source/Rental_Agent_Prototype_Architecture.pdf). Searchable text: [architecture.txt](source/architecture.txt). Figures: [source/diagrams/](source/diagrams/).

Change history and decisions: [CLAUDE_CHANGELOG.md](../CLAUDE_CHANGELOG.md).

## Documents

- [PRD.md](PRD.md): purpose, goals, users, in-scope and out-of-scope items.
- [FRD.md](FRD.md): functional requirements (FR-xx), business rules, error cases, change state table.
- [ARCHITECTURE.md](ARCHITECTURE.md): system context, components, deployment options, data model.
- [AI_PIPELINE.md](AI_PIPELINE.md): model roles, visitor and back-office pipelines, agent loop rules, guardrail order.
- [API.md](API.md): every endpoint with method, path, auth, success and errors.
- [TOOLS.md](TOOLS.md): every tool with role, input, side effect and notes.
- [DATA_FLOWS.md](DATA_FLOWS.md): parity check, change lifecycle, visitor journey.
- [SECURITY.md](SECURITY.md): trust boundaries, secrets handling, security rules.
- [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md): AC-1 to AC-7 with steps, expected results and test functions.
- [REQUIREMENTS.md](REQUIREMENTS.md): environment, dependencies, non-functional requirements.
- [DECISIONS.md](DECISIONS.md): architecture decision records ADR-01 to ADR-07.
- [ASSUMPTIONS.md](ASSUMPTIONS.md): assumptions register, scaffold reconciliation, PDF ambiguities.

## Suggested reading order

1. [PRD.md](PRD.md): what is being built and why.
2. [ARCHITECTURE.md](ARCHITECTURE.md): how the pieces fit.
3. [AI_PIPELINE.md](AI_PIPELINE.md): how a chat turn runs.
4. [DATA_FLOWS.md](DATA_FLOWS.md): parity, approvals, visitor limit.
5. [FRD.md](FRD.md): the detailed requirements.
6. [API.md](API.md) and [TOOLS.md](TOOLS.md): interfaces.
7. [SECURITY.md](SECURITY.md): rules enforced in code.
8. [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md): how done is checked.
9. [REQUIREMENTS.md](REQUIREMENTS.md): what you need to run it.
10. [DECISIONS.md](DECISIONS.md): why it is designed this way.
11. [ASSUMPTIONS.md](ASSUMPTIONS.md): what is still open.
