# Acceptance Tests

Source: [Rental_Agent_Prototype_Architecture.pdf](source/Rental_Agent_Prototype_Architecture.pdf), section 10.

Each test is one function in `tests/test_acceptance.py`. The model is replaced by a scripted fake in every test except one optional live test that runs against Bedrock when AWS credentials are present. [ASSUMPTION: the live test's name and the fake's design are not specified; see A-15 and SR-07.]

Preconditions and steps below are derived from the PDF's pipelines and data flows. Where the PDF does not give a detail (seed values, KB content), the step says so and links to the assumption.

## Summary

| Test | Function | Behaviour checked | Diagram | Pass condition |
|------|----------|-------------------|---------|----------------|
| AC-1 | `test_ac1` | Knowledge question returns a cited answer | Fig. 5 stages 3 to 7 | Reply contains an approved `[kb:ID]` |
| AC-2 | `test_ac2` | Unknown question returns a hand-off, no guess | Fig. 5 stage 6 | Hand-off offer, `handoffs` row written |
| AC-3 | `test_ac3` | Sixth visitor message returns the registration prompt | Fig. 5 stage 2, Fig. 9 | Prompt returned; model not called |
| AC-4 | `test_ac4` | Seeded rate mismatch is reported, nothing changes | Fig. 7 | `gaps` row exists; `pms_rates` unchanged |
| AC-5 | `test_ac5` | Change has no effect until approved; then applied and logged | Fig. 6, Fig. 8 | Applied only after approval; log rows present |
| AC-6 | `test_ac6` | Guest-messaging request is refused and logged | Fig. 5 stage 1, Fig. 6 | Refusal text; log row; model not called |
| AC-7 | `test_ac7` | `change_log` rows cannot be updated or deleted | Fig. 4, Fig. 10 | UPDATE and DELETE both fail |

## AC-1: Knowledge question returns a cited answer

- Function: `test_ac1`
- Diagram: [Figure 5](source/diagrams/figure_05.png), stages 3 to 7.
- Preconditions: project loaded with at least one KB file with status `approved`; visitor session under the free-message limit; scripted fake model returns a reply citing that entry's `[kb:ID]`. [ASSUMPTION: KB file format and ID scheme are not specified.] (A-19)
- Steps: `POST /api/chat` with a question answered by the approved entry.
- Expected: 200; reply contains an approved `[kb:ID]`; `message_count` incremented; one `traces` row written.

## AC-2: Unknown question returns a hand-off, no guess

- Function: `test_ac2`
- Diagram: [Figure 5](source/diagrams/figure_05.png), stage 6.
- Preconditions: as AC-1; scripted fake model returns a reply with no approved `[kb:ID]` citation.
- Steps: `POST /api/chat` with a question not covered by approved files.
- Expected: reply is a hand-off offer; a `handoffs` row is written.

## AC-3: Sixth visitor message returns the registration prompt

- Function: `test_ac3`
- Diagrams: [Figure 5](source/diagrams/figure_05.png) stage 2, [Figure 9](source/diagrams/figure_09.png).
- Preconditions: unregistered visitor session; free messages = 5.
- Steps: send five messages via `POST /api/chat`; send a sixth.
- Expected: messages 1 to 5 are answered; message 6 returns the registration prompt; the model is not called for message 6. (Counter timing: PA-01.)

## AC-4: Seeded rate mismatch is reported, nothing changes

- Function: `test_ac4`
- Diagram: [Figure 7](source/diagrams/figure_07.png).
- Preconditions: `data/*.json` seeds a `pms_rates` value and a `channel_rates` value that differ for the same listing and date; parity tolerance 0; staff session. [ASSUMPTION: seed values are not specified.] (A-03)
- Steps: `POST /api/parity/run` with that listing_id, start, end; then `GET /api/parity`.
- Expected: a `gaps` row exists for that listing, channel and date; `pms_rates` is unchanged.

## AC-5: Change has no effect until approved; then applied and logged

- Function: `test_ac5`
- Diagrams: [Figure 6](source/diagrams/figure_06.png), [Figure 8](source/diagrams/figure_08.png).
- Preconditions: staff session; a seeded rate whose current value is known.
- Steps:
  1. `POST /api/changes` with a correct before value.
  2. Read the rate: it is unchanged; change is `awaiting_approval`.
  3. `POST /api/changes/{id}/approve` with an approver name.
  4. Read the rate and `GET /api/changelog`.
- Expected: the rate changes only after approval; final state `verified`; `change_log` rows present for each transition.

## AC-6: Guest-messaging request is refused and logged

- Function: `test_ac6`
- Diagrams: [Figure 5](source/diagrams/figure_05.png) stage 1, [Figure 6](source/diagrams/figure_06.png).
- Preconditions: any session.
- Steps: `POST /api/chat` asking to message, email or contact a guest.
- Expected: refusal text returned; a log row is written (refusal written to `change_log`); the model is not called. (Log row shape: PA-02.)

## AC-7: change_log rows cannot be updated or deleted

- Function: `test_ac7`
- Diagrams: [Figure 4](source/diagrams/figure_04.png), [Figure 10](source/diagrams/figure_10.png).
- Preconditions: database initialised with triggers; at least one `change_log` row.
- Steps: attempt `UPDATE change_log ...`; attempt `DELETE FROM change_log ...`.
- Expected: UPDATE and DELETE both fail.

## Current status

All seven are implemented and pass (PR #2). The scripted fake model is `FakeModel` in `tests/conftest.py`. `tests/test_rules.py` covers the supporting rules: step limit, allowlist and schema errors, draft citations, stale proposals, rejection, hash mismatch, payment masking, auth and error codes. The optional live test is `tests/test_live_bedrock.py`, which runs only when `RUN_LIVE_BEDROCK=1` (resolves A-15 and SR-07).

Implementation notes for the tests:

- AC-3 follows PA-01 / D-06: the counter blocks when `message_count >= free_messages`, and blocked messages are counted too.
- AC-4 uses the seeded mismatch on `L-100` / `channel_a` / 2026-12-05 (PMS 180, channel 175); 2026-12-07 has no channel rate and is reported as no data.
- AC-6 runs for both a visitor and a staff session; the refusal row has `event = 'refusal'` and no `change_id` (D-05).
