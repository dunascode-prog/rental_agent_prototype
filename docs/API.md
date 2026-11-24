# API Reference

Source: [Rental_Agent_Prototype_Architecture.pdf](source/Rental_Agent_Prototype_Architecture.pdf), section 7. Route map: [Figure 2](source/diagrams/figure_02.png).

All routes are served by `main.py`. Staff routes need a logged-in session. The prototype has a single staff login per project; [ASSUMPTION: staff accounts are created by the project owner in config, not by self-service registration.] (A-02)

Request and response body shapes are not specified in the PDF. [ASSUMPTION: field names below are taken from the tool inputs (PDF section 8) and the data model (Figure 4) where they exist; anything else is to be defined during implementation.] (A-07)

## Summary

| Method | Path | Purpose | Auth | Success | Main errors |
|--------|------|---------|------|---------|-------------|
| GET | `/health` | Liveness check | none | 200 `{status: ok}` | none |
| POST | `/api/chat` | One visitor or staff chat turn | session cookie | 200 reply and state | 400 bad input, 429 too many requests |
| POST | `/api/register` | Create an account | none | 201 user created | 409 email exists, 400 invalid |
| GET | `/api/parity` | Gaps for a listing | session (staff) | 200 gaps list | 404 unknown listing |
| POST | `/api/parity/run` | Run a parity check | session (staff) | 200 run summary | 409 run already active |
| POST | `/api/changes` | Propose a rate change | session (staff) | 201 pending change | 409 before value is stale, 400 invalid |
| POST | `/api/changes/{id}/approve` | Approve with approver name | session (staff) | 200 approved, then applied | 403 no name, 409 hash mismatch or wrong state |
| POST | `/api/changes/{id}/reject` | Reject a pending change | session (staff) | 200 rejected | 409 wrong state |
| GET | `/api/changelog` | Read the change log | session (staff) | 200 log rows | none |

## Endpoints

### GET /health

- Purpose: liveness check.
- Auth: none.
- Success: `200 {"status": "ok"}`. Implemented in the scaffold (`app/main.py`).
- Errors: none.

### POST /api/chat

- Purpose: one visitor or staff chat turn. Runs the visitor pipeline ([Figure 5](source/diagrams/figure_05.png)) or the back-office pipeline ([Figure 6](source/diagrams/figure_06.png)).
- Auth: session cookie. The cookie token is `sessions.id` (Fig. 4).
- Success: 200 reply and state.
  - Guest-messaging request: refusal text (model not called).
  - Sixth unregistered visitor message: registration prompt (model not called).
  - Otherwise: model reply, or hand-off offer if the reply had no approved `[kb:ID]` citation.
- Errors: 400 bad input; 429 too many requests. [ASSUMPTION: the PDF does not say what triggers 429; it is not the free-message limit, which returns a prompt (AC-3).] (PA-08)

### POST /api/register

- Purpose: create an account ([Figure 9](source/diagrams/figure_09.png)).
- Auth: none.
- Input: email + password (Fig. 9; `auth.py` inputs).
- Behaviour: password hashed with argon2 (or bcrypt if argon2 is not available); `users` row created; session linked to `user_id`; chat unlocked for this user.
- Success: 201 user created.
- Errors: 409 email exists; 400 invalid. [ASSUMPTION: password length rule is a default not given in the PDF.] (A-04)

### GET /api/parity

- Purpose: gaps for a listing.
- Auth: session (staff).
- Input: a listing identifier. [ASSUMPTION: parameter name `listing_id`, matching `list_gaps` input.] (A-16)
- Success: 200 gaps list (rows from `gaps`).
- Errors: 404 unknown listing.

### POST /api/parity/run

- Purpose: run a parity check ([Figure 7](source/diagrams/figure_07.png)). Plain code, no model involved.
- Auth: session (staff).
- Input: `listing_id`, `start`, `end` (Fig. 7 trigger).
- Success: 200 run summary (count of gaps, `run_id`).
- Errors: 409 run already active.
- Side effect: writes `gaps` rows only. No rate is changed.

### POST /api/changes

- Purpose: propose a rate change ([Figure 8](source/diagrams/figure_08.png)).
- Auth: session (staff).
- Input: `type`, `target`, `before`, `after` (from `propose_change`, PDF section 8). [ASSUMPTION: how `target` maps to `listing_id`, `channel`, `date` in `changes` is not specified.] (A-10)
- Behaviour: before value checked against `pms_rates`; `changes` row created in `proposed`, then `awaiting_approval`.
- Success: 201 pending change.
- Errors: 409 before value is stale (state `rejected_at_proposal`); 400 invalid.

### POST /api/changes/{id}/approve

- Purpose: approve with approver name.
- Auth: session (staff).
- Input: approver name (approval card name box, Fig. 6).
- Behaviour: approve endpoint recomputes the `change_hash` before accepting; `approvals` row stores `change_hash`; apply and the state change run in one database transaction; value re-read to verify.
- Success: 200 approved, then applied. [ASSUMPTION: the response reports the resulting state, `verified` or `failed`.] (PA-09)
- Errors: 403 no name; 409 hash mismatch or wrong state.

### POST /api/changes/{id}/reject

- Purpose: reject a pending change.
- Auth: session (staff).
- Success: 200 rejected (state `rejected`, nothing applied, logged).
- Errors: 409 wrong state.

### GET /api/changelog

- Purpose: read the change log.
- Auth: session (staff).
- Success: 200 log rows (`change_log`: id, change_id, event, from_state, to_state, actor, payload_hash, at).
- Errors: none.

## Implemented request bodies (resolves A-07)

| Endpoint | Body |
|----------|------|
| `POST /api/chat` | `{"message": string (1-4000)}` → `{"reply", "state": {role, registered, email, messages_used, free_messages, limited, model_called, pending_changes, outcome}}`; `outcome` is `answered`, `handoff`, `fallback`, `refuse` or `register` |
| `POST /api/register`, `POST /api/login` | `{"email", "password"}` |
| `GET /api/parity` | query `listing_id` (A-16) |
| `POST /api/parity/run` | `{"listing_id", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}` |
| `POST /api/changes` | `{"type": "rate_update", "target": {"listing_id", "date", "channel"?}, "before", "after"}`; omit `channel` to change the PMS rate (A-10) |
| `POST /api/changes/{id}/approve` | `{"approver_name", "change_hash"?}`; when `change_hash` is sent it must match the recomputed hash |

Unknown fields are rejected with 400. Responses with a change include the full `changes` row and its `approval`. The approve endpoint returns the final state, `verified` or `failed` (PA-09).

## Additional routes (decision D-02)

Not in the PDF; added so staff can log in and the UI can rebuild its panels after a reload.

| Method | Path | Purpose | Auth | Success | Main errors |
|--------|------|---------|------|---------|-------------|
| POST | `/api/login` | Log in (staff or registered visitor) | none | 200 state | 401 wrong email or password |
| POST | `/api/logout` | Unlink the user from the session | session cookie | 200 | none |
| GET | `/api/session` | Project name and session state | session cookie | 200 state | none |
| GET | `/api/listings` | Listings for the parity panel | session (staff) | 200 listings | 401, 403 |
| GET | `/api/changes` | Changes, optionally `?state=awaiting_approval` | session (staff) | 200 changes | 401, 403 |

Staff routes return 401 without a logged-in user and 403 for a non-staff user. `POST /api/chat` returns 429 after `chat_rate_limit_per_minute` requests per session per minute (D-12).

## Related documents

- Functional requirements and error table: [FRD.md](FRD.md)
- Tools that back these endpoints: [TOOLS.md](TOOLS.md)
