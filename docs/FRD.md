# Functional Requirements Document (FRD)

Source: [Rental_Agent_Prototype_Architecture.pdf](source/Rental_Agent_Prototype_Architecture.pdf), sections 2, 4 and 9 (with sections 3, 5, 7, 8 where a requirement depends on them).

FR IDs are defined in this document. Each requirement names its PDF source. Items not stated in the PDF are marked [ASSUMPTION] and listed in [ASSUMPTIONS.md](ASSUMPTIONS.md).

## 1. Platform and project loading

| ID | Requirement | Source |
|----|-------------|--------|
| FR-01 | The service is one FastAPI process with one SQLite file. A browser page (`static/index.html`) talks to it over HTTP. | §2, [Fig. 2](source/diagrams/figure_02.png) |
| FR-02 | `GET /health` returns `200 {status: ok}` with no auth. | §7 |
| FR-03 | `config.py` loads the project folder and validates `config.yaml`, the KB and the data files, producing a Project object. | §6, [Fig. 2](source/diagrams/figure_02.png) |
| FR-04 | `db.py` creates the schema and triggers, and seeds data from `data/*.json`. | §6 |
| FR-05 | Only KB files with status `approved` are loaded (`kb/*.md (approved only)`). | [Fig. 2](source/diagrams/figure_02.png), [Fig. 5](source/diagrams/figure_05.png) stage 3 |
| FR-06 | The tool allowlist for each project comes from config. | §6, [Fig. 2](source/diagrams/figure_02.png) |

## 2. Visitor chat (sales role)

Diagram: [Figure 5](source/diagrams/figure_05.png).

| ID | Requirement | Source |
|----|-------------|--------|
| FR-10 | `POST /api/chat` runs one visitor or staff chat turn, identified by the session cookie. Returns `200 reply and state`. | §7 |
| FR-11 | Stage 1 intent check: if the message asks to message or contact a guest, return refusal text, write the refusal to `change_log`, and do not call the model. | Fig. 5 stage 1, §1 |
| FR-12 | Stage 2 message counter: a visitor who is not registered gets five free messages. The sixth message returns the registration prompt and the model is not called. The count is kept on the server (`sessions.message_count`). | §1, Fig. 5 stage 2, [Fig. 9](source/diagrams/figure_09.png) |
| FR-13 | Stage 3 builds the context: system prompt (persona, rules), approved KB files only (status: approved), price sheet rules, last N turns of this session, tools allowed by `config.yaml`. [ASSUMPTION: the value of N is not given; see A-08.] | Fig. 5 stage 3 |
| FR-14 | Stage 4 calls Bedrock (Claude Haiku) with max tokens from config. | Fig. 5 stage 4, §3 |
| FR-15 | Visitor chat tools are `search_kb`, `get_price_sheet`, `handoff_to_sales`. `get_price_sheet` is the only source of prices. | §3, §8 |
| FR-16 | Stage 6 output check: if the reply does not cite `[kb:ID]` of an approved entry, it is replaced with a hand-off offer and a row is written to `handoffs`. | Fig. 5 stage 6 |
| FR-17 | Stage 7 saves and traces: `message_count + 1`, one `traces` row written. | Fig. 5 stage 7 |

## 3. Registration

Diagram: [Figure 9](source/diagrams/figure_09.png).

| ID | Requirement | Source |
|----|-------------|--------|
| FR-20 | `POST /api/register` creates an account from email and password; returns `201 user created`. | §7, Fig. 9 |
| FR-21 | Passwords are hashed with argon2 (or bcrypt if argon2 is not available) and never logged. | §5 |
| FR-22 | On registration a `users` row is created and the session is linked to `user_id`. Chat is unlocked for this user (counter no longer applies). | Fig. 9 |
| FR-23 | A visitor who leaves without registering keeps the counter at 6. | Fig. 9 |

## 4. Agent loop (both roles)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-30 | The loop stops after 8 model calls and returns a safe fallback reply (offer hand-off). | §3 agent loop rules, Fig. 5 |
| FR-31 | A tool request that is not on the allowlist, or whose input does not match its schema, returns an error to the model and has no side effects. | §3, Fig. 5 stage 5 |
| FR-32 | Each turn writes one `traces` row: model ID, tools called, token counts and elapsed time. | §3 |
| FR-33 | The model never receives credentials, and the system prompt contains only approved content for the project. | §3 |

## 5. Back-office role

Diagram: [Figure 6](source/diagrams/figure_06.png).

| ID | Requirement | Source |
|----|-------------|--------|
| FR-40 | Staff routes need a logged-in session (`session (staff)`). Single staff login per project. [ASSUMPTION: staff accounts are created by the project owner in config; A-02.] | §7 |
| FR-41 | The back-office request runs the same intent check: guest messaging is refused, logged to `change_log`, and the turn stops. | Fig. 6 |
| FR-42 | Back-office tools: `get_listing`, `get_reservation`, `run_parity_check`, `list_gaps`, `propose_change`, `get_change_status`, `handoff_to_human`. There is no messaging tool. | §3, §8 |
| FR-43 | `get_reservation` returns payment details masked to the last four digits, in every output and log. | §5, §8 |
| FR-44 | `handoff_to_human` writes a `handoffs` row; used when staff need a person. | §8 |

## 6. Parity check

Diagram: [Figure 7](source/diagrams/figure_07.png). Data flow detail: [DATA_FLOWS.md](DATA_FLOWS.md#1-parity-check).

| ID | Requirement | Source |
|----|-------------|--------|
| FR-50 | `POST /api/parity/run` (listing_id, start, end) runs a parity check in plain code; no model is involved. Returns `200 run summary` (count of gaps, run_id). | §7, Fig. 7 |
| FR-51 | The check reads `pms_rates` for the listing and each date, and `channel_rates` for each channel and date, then joins on (listing_id, date). | Fig. 7 |
| FR-52 | Missing values on either side are reported as 'no data' and are not counted as gaps. | Fig. 7 caption |
| FR-53 | Rates are compared using the tolerance from config (0). Equal values produce no record; different values write one `gaps` row (run_id, listing, channel, date, pms_rate, channel_rate, found_at). | Fig. 7 |
| FR-54 | No rate is changed by the parity check. | Fig. 7, §8 (`run_parity_check`: never changes rates) |
| FR-55 | `GET /api/parity` returns the gaps for a listing (`200 gaps list`). `list_gaps` returns open gaps only. | §7, §8 |

## 7. Change lifecycle and approval

Diagrams: [Figure 6](source/diagrams/figure_06.png), [Figure 8](source/diagrams/figure_08.png).

| ID | Requirement | Source |
|----|-------------|--------|
| FR-60 | `propose_change` / `POST /api/changes` creates a `changes` row in state `proposed` after checking the before value against `pms_rates`. Returns `201 pending change`. | §7, §8, Fig. 8 |
| FR-61 | If the before value no longer matches PMS, the change goes to `rejected_at_proposal`. | §9, Fig. 8 |
| FR-62 | A valid proposal moves to `awaiting_approval` and an approval card is shown with before and after values and an approver name box. | §9, Fig. 6 |
| FR-63 | `POST /api/changes/{id}/approve` requires an approver name; the approval row stores the `change_hash`, and the endpoint recomputes the hash before accepting. | §7, §9 |
| FR-64 | Apply and the state change run in one database transaction. If the transaction fails, nothing is written. Apply writes to `pms_rates` or `channel_rates`. | §9, Fig. 8 |
| FR-65 | After apply, the value is re-read. If it equals the after value the state is `verified`; otherwise `failed` and an alert is shown. | §9, Fig. 6, Fig. 8 |
| FR-66 | `POST /api/changes/{id}/reject` moves an `awaiting_approval` change to `rejected`; nothing is applied. | §7, §9 |
| FR-67 | Each transition writes one `change_log` row containing the previous state, the new state, the actor, the payload hash and the time. | §9, Fig. 8 |
| FR-68 | `GET /api/changelog` returns log rows (`200 log rows`). | §7 |
| FR-69 | `change_log` is append-only: database triggers reject UPDATE and DELETE. | §5, Fig. 4 |
| FR-70 | Only the rate-update change type is built. | §11 |

## 8. Business rules

| ID | Rule | Source |
|----|------|--------|
| BR-01 | Answers come only from approved content. If the answer is not in approved files, offer a hand-off and do not guess. | §1 |
| BR-02 | Five free visitor messages; the count is kept on the server. | §1 |
| BR-03 | Nothing changes until a named person approves it. The state changes in Fig. 8 are the only way a rate changes. | §1, Fig. 8 |
| BR-04 | Approval is valid only for the exact change it was given for (`change_hash`). | §9 |
| BR-05 | Guest messaging is refused before the model runs, and the refusal is logged. | §8 |
| BR-06 | Rates in `pms_rates` are changed only through the approval flow. | Fig. 4 caption |
| BR-07 | Parity tolerance comes from config (0). | Fig. 7 |
| BR-08 | Every rule that matters is enforced in server code, not in the prompt. | Fig. 10 caption |
| BR-09 | Single approver per project. No roles. | §11 |

## 9. Error cases

| Endpoint | Condition | Response | Source |
|----------|-----------|----------|--------|
| `POST /api/chat` | Bad input | 400 | §7 |
| `POST /api/chat` | Too many requests | 429 [ASSUMPTION: trigger not specified; see PA-08] | §7 |
| `POST /api/register` | Email exists | 409 | §7 |
| `POST /api/register` | Invalid | 400 | §7 |
| `GET /api/parity` | Unknown listing | 404 | §7 |
| `POST /api/parity/run` | Run already active | 409 | §7 |
| `POST /api/changes` | Before value is stale | 409 | §7 |
| `POST /api/changes` | Invalid | 400 | §7 |
| `POST /api/changes/{id}/approve` | No name | 403 | §7 |
| `POST /api/changes/{id}/approve` | Hash mismatch or wrong state | 409 | §7 |
| `POST /api/changes/{id}/reject` | Wrong state | 409 | §7 |
| Any tool call | Tool not on allowlist or input does not match schema | Error returned to model, no side effects | §3 |
| Agent loop | 8 model calls reached | Safe fallback reply (offer hand-off) | §3, Fig. 5 |
| Verification | Re-read does not match | State `failed`, alert shown | §9 |

## 10. Change state table

Copied from PDF section 9. Diagram: [Figure 8](source/diagrams/figure_08.png).

| State | Meaning | Allowed next states | Trigger |
|-------|---------|---------------------|---------|
| `proposed` | Change row created | `awaiting_approval`, `rejected_at_proposal` | `propose_change` succeeded |
| `awaiting_approval` | Waiting for a person | `approved`, `rejected` | Approval card shown |
| `approved` | Named approver recorded | `applied` | Approve endpoint, hash matches |
| `applied` | Value written to `pms_rates` or `channel_rates` | `verified`, `failed` | Apply step finished |
| `verified` | Re-read value equals the after value | none (end) | Verification passed |
| `failed` | Re-read does not match | none (end; alert shown) | Verification failed |
| `rejected` | Person rejected the change | none (end) | Reject endpoint |
| `rejected_at_proposal` | Before value no longer matches PMS | none (end) | Stale check failed |

The API and tool tables use the word "pending" for a new change; this document reads it as `proposed`/`awaiting_approval` (see PA-03 in [ASSUMPTIONS.md](ASSUMPTIONS.md#pdf-ambiguities)).
