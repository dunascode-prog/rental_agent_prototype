# Product Requirements Document (PRD)

Source: [Rental_Agent_Prototype_Architecture.pdf](source/Rental_Agent_Prototype_Architecture.pdf), section 1 and section 11.
Context diagram: [Figure 1](source/diagrams/figure_01.png).

## 1. Purpose

The prototype is a small, working version of the two-agent system in the job specification. It keeps the rules that matter most:

- answers come only from approved content,
- changes need a named approver,
- every action is logged,
- guest messaging is refused.

It uses mock data for the property management system (PMS) and the booking channels, and does not connect to real payment or booking systems.

Model provider: Amazon Bedrock (Claude). Runs locally first; optional AWS deployment.

## 2. Goals

| ID | Goal | Measured by |
|----|------|-------------|
| G-1 | Visitor questions are answered only from approved knowledge-base files, with the file cited | AC-1, AC-2 |
| G-2 | Visitors get five free messages, then are asked to register; the count is kept on the server | AC-3 |
| G-3 | Rate differences between the mock PMS and a mock booking channel are reported as gaps, with nothing changed | AC-4 |
| G-4 | A rate change has no effect until a named person approves it; it is then applied and re-read to verify it | AC-5 |
| G-5 | Requests to message, email or contact a guest are refused and logged | AC-6 |
| G-6 | The change log cannot be edited or deleted by the application | AC-7 |

Acceptance tests are defined in [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md).

## 3. Users

From [Figure 1](source/diagrams/figure_01.png):

| User | Description | What they do |
|------|-------------|--------------|
| Website visitor | Prospective customer | Chat, register |
| Property staff | Back-office user | Parity check, approve or reject change, change log |
| Project owner | Edits KB, config, price sheet | Writes and approves content; provides `config.yaml` |

Staff routes need a logged-in session. The prototype has a single staff login per project. [ASSUMPTION: staff accounts are created by the project owner in config, not by self-service registration.] (PDF section 7; see [A-02](ASSUMPTIONS.md#register).)

## 4. In scope

What the prototype does (PDF section 1):

1. Answers website visitor questions from approved knowledge-base files, citing the file used. If the answer is not in those files, it offers a hand-off to a person and does not guess.
2. Allows five free visitor messages, then asks the visitor to register. The count is kept on the server.
3. Compares rates between a mock property system and a mock booking channel, and reports each difference as a gap.
4. Proposes a rate change. Nothing changes until a named person approves it; the change is then applied and re-read to verify it.
5. Keeps a change log that the application cannot edit or delete.
6. Refuses any request to message, email or contact a guest, and logs the refusal. No messaging tool exists.

## 5. Out of scope

What the prototype does not do (PDF section 1):

- Connect to a real property management system, booking channel, billing system or payment provider.
- Provide the Chrome extension, multiple approvers, roles, several languages, date changes or payment requests.
- Use vector search. The approved knowledge base is loaded into the model's context.

After the prototype (not in scope, PDF section 11):

- Real PMS connectors (API first, Playwright browser fallback), then real channel connectors.
- Chrome extension for the back-office chat and approval cards.
- Stripe test-mode checkout, upgrade, downgrade and cancellation.
- Vector search for larger knowledge bases; PostgreSQL with pgvector.
- Multiple approvers, roles, email verification, monitoring and alerting.

## 6. Known limits (accepted for the prototype)

From PDF section 11:

- Clearing cookies starts a new visitor session, so the message limit can be reset this way. Accepted for the prototype.
- No email verification after registration.
- A single approver per project. No roles.
- Only the rate-update change type is built. Date changes and payment requests are designed but not implemented.
- Model cost depends on usage; Bedrock access and pricing must be checked before use.

## 7. Assumptions

The PDF marks these as unconfirmed. Full register: [ASSUMPTIONS.md](ASSUMPTIONS.md).

- [ASSUMPTION] Mock data stands in for the PMS and booking channels. Real connectors are a later phase. (A-03)
- [ASSUMPTION] Local development is the default. A hosted demo is optional and needs a persistent volume or another database. (A-05)
- [ASSUMPTION] Claude models on Bedrock are available in the chosen region and enabled for the account. (A-06)

## 8. Related documents

- Functional detail: [FRD.md](FRD.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Index and reading order: [INDEX.md](INDEX.md)
