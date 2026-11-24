# Requirements: Environment, Dependencies, Non-functional

Sources: [Rental_Agent_Prototype_Architecture.pdf](source/Rental_Agent_Prototype_Architecture.pdf) sections 2, 5 and 11; the project scaffold (`requirements.txt`, `.env.example`). Deployment diagram: [Figure 3](source/diagrams/figure_03.png).

## 1. Environment requirements

| ID | Requirement | Source |
|----|-------------|--------|
| ENV-01 | Python 3.12 | Scaffold (not stated in the PDF; A-14) |
| ENV-02 | Virtual environment in `.venv`; app started as `uvicorn app.main:app`, browsed at `localhost:8000` | Fig. 3 Option A |
| ENV-03 | An AWS account with Amazon Bedrock access | §2, §3 |
| ENV-04 | Bedrock model access enabled for the Claude models used by each role. Copy the exact model IDs (`<bedrock-model-id>`) and region (`<aws-region>`) from the Bedrock console | §3 |
| ENV-05 | [ASSUMPTION] Claude models on Bedrock are available in the chosen region and enabled for the account | §11 (A-06) |
| ENV-06 | AWS credentials via an AWS profile or environment variables; `.env` (AWS profile, region), not committed | §5, Fig. 3 |
| ENV-07 | IAM permission limited to model invocation (`bedrock:InvokeModel` only in the PDF; `bedrock-mantle:CreateInference` only since D-01 moved the client to Mantle) | §5, Fig. 3, D-01 |
| ENV-08 | Bedrock region the same as config | Fig. 3 Option B (see PA-10) |
| ENV-09 | Optional hosted demo: container service (App Runner or one small ECS task), Docker image of the app, persistent volume for SQLite | Fig. 3 Option B, §11 (A-05) |

Environment variables (from `.env.example`): `AWS_PROFILE`, `AWS_REGION`, `APP_SECRET_KEY`, `DATABASE_PATH`. Values are never committed.

## 2. Dependencies

| Package (`requirements.txt`) | Purpose | PDF reference |
|------------------------------|---------|---------------|
| `fastapi` | Web app, routes | §2 "one FastAPI process" |
| `uvicorn[standard]` | ASGI server | Fig. 3 `uvicorn app.main:app` |
| `pydantic` | Request validation | §6 `main.py` "request validation" (library not named in PDF) |
| `pyyaml` | Load `config.yaml` | §6 `config.py` depends on yaml |
| `anthropic` | Bedrock client (Anthropic SDK, Bedrock mode) | §6 `model.py`, Fig. 2 |
| `boto3` | AWS credentials and SDK support | Not named in PDF; scaffold choice (SR-12) |
| `passlib[argon2]` | argon2 password hashing | §5, §6 `auth.py` depends on argon2 |
| `pytest` | Acceptance tests | §10 `tests/test_acceptance.py` |
| `httpx` | HTTP test client | Not named in PDF; scaffold choice |

Standard library: `sqlite3` (§6 `db.py`).

## 3. Non-functional requirements

| ID | Requirement | Source |
|----|-------------|--------|
| NFR-01 | Single process: one FastAPI process with one SQLite file | §2 |
| NFR-02 | Local first; Option A is the default with $0 hosting | §2, Fig. 3 |
| NFR-03 | Persistence: a container service without a persistent volume loses the SQLite data on restart; it must use a volume or a different database before any shared demo | Fig. 3 caption |
| NFR-04 | Cost control: stages 1 and 2 run before the model is called so refusals and the registration prompt cost nothing | Fig. 5 caption |
| NFR-05 | Bounded model use: the loop stops after 8 model calls | §3 |
| NFR-06 | Observability: each turn writes one `traces` row (model ID, tools called, token counts, elapsed time) | §3 |
| NFR-07 | Auditability: every transition writes one `change_log` row; the table is append-only via triggers | §5, §9 |
| NFR-08 | Atomicity: apply and the state change run in one database transaction | §9 |
| NFR-09 | Passwords hashed with argon2 (or bcrypt if argon2 is not available); never logged | §5 |
| NFR-10 | Payment details masked to the last four digits in every output and log | §5 |
| NFR-11 | Parameterised queries only | §5 |
| NFR-12 | Secrets never in project files; real `.env` excluded from version control | §5 |
| NFR-13 | Model cost depends on usage; Bedrock access and pricing must be checked before use | §11 |
| NFR-14 | Rules enforced in server code, not in the prompt | Fig. 10 |

## 4. Defaults not specified

[ASSUMPTION] The retrieval threshold, password length and transcript retention are defaults (PDF §11). Their values are not in the PDF; see A-04 in [ASSUMPTIONS.md](ASSUMPTIONS.md).
