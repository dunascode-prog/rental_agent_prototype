# Architecture Decision Records

Source: [Rental_Agent_Prototype_Architecture.pdf](source/Rental_Agent_Prototype_Architecture.pdf). Each record states the decision as it appears in the PDF. Status for all: Accepted (design baseline for the prototype build).

ADR IDs are defined in this document.

## ADR-01: Single process

- Context: the prototype is a small, working version of the two-agent system (§1).
- Decision: the service is one FastAPI process with one SQLite file. A browser page talks to it over HTTP (§2). Both roles run on the same runtime (§3).
- Consequences: one deployable unit (`uvicorn app.main:app` locally, one container for Option B, [Figure 3](source/diagrams/figure_03.png)). No inter-service calls. Not designed for horizontal scaling.
- Diagram: [Figure 2](source/diagrams/figure_02.png).

## ADR-02: Parity checks in code

- Context: rates must be compared between the mock PMS and a mock booking channel (§1).
- Decision: the parity check is plain code, no model involved: two reads, one join, one comparison, tolerance from config (0). `parity.py` is the parity engine (§4, [Figure 7](source/diagrams/figure_07.png), [Figure 2](source/diagrams/figure_02.png)).
- Consequences: deterministic results; missing values reported as 'no data', not gaps; the flow never changes rates. The model can only trigger it through `run_parity_check`.

## ADR-03: Approval as a database state machine

- Context: nothing may change until a named person approves it (§1).
- Decision: a rate change moves through the states `proposed`, `awaiting_approval`, `approved`, `applied`, `verified` / `failed`, with `rejected` and `rejected_at_proposal` as end states (§9, [Figure 8](source/diagrams/figure_08.png)). The approval row stores the `change_hash` and the approve endpoint recomputes it. Apply and the state change run in one transaction. Each transition writes one `change_log` row.
- Consequences: the state changes in Fig. 8 are the only way a rate changes. The model can only propose (`propose_change`); approval comes through `POST /api/changes/{id}/approve`. A single approver per project (§11).

## ADR-04: SQLite for the prototype

- Context: local-first prototype with $0 hosting by default (Fig. 3).
- Decision: storage is one SQLite file accessed through `sqlite3` (§2, §6). `change_log` is protected by database triggers (§5).
- Consequences: no database server to run. A container service without a persistent volume loses the data on restart, so it must use a volume or a different database before any shared demo (Fig. 3). Later phase: PostgreSQL with pgvector (§11).
- Diagram: [Figure 4](source/diagrams/figure_04.png).

## ADR-05: Knowledge base in context

- Context: answers must come only from approved content (§1).
- Decision: no vector search. The approved knowledge base is loaded into the model's context (§1). Only KB files with status approved are included (Fig. 5 stage 3).
- Consequences: simple retrieval for small knowledge bases; answers must cite `[kb:ID]` or are replaced by a hand-off offer. Vector search for larger knowledge bases is after the prototype (§11).
- Diagram: [Figure 5](source/diagrams/figure_05.png).

## ADR-06: Amazon Bedrock as the model provider

- Context: model provider for both roles.
- Decision: Amazon Bedrock (Claude), called by `model.py` through the Anthropic SDK in Bedrock mode with AWS credentials; InvokeModel (AWS SigV4) (§2, §6, Fig. 2). Visitor chat uses Claude Haiku; back-office uses Claude Sonnet; model IDs are set in `config.yaml` and copied from the Bedrock console (§3).
- Consequences: no Anthropic API key; AWS credentials are used only by the Bedrock client (Fig. 10); IAM limited to model invocation (§5). Depends on model availability in the chosen region (A-06). Model choice may change after testing (A-01).

## ADR-07: Guardrails enforced in code

- Context: visitor text and model output are untrusted ([Figure 10](source/diagrams/figure_10.png)).
- Decision: every rule that matters is enforced in server code, not in the prompt. The checks that decide whether something is allowed run in code, before and after the model (§3): intent check and message counter before the model; tool allowlist and schema check before any tool runs; approval gate and hash check before any data change; output citation check after the model (`guardrails.py`).
- Consequences: refusals and the registration prompt cost nothing and cannot be talked around (Fig. 5). There is no messaging tool for either role (§8).
