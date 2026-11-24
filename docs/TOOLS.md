# Tool Reference

Source: [Rental_Agent_Prototype_Architecture.pdf](source/Rental_Agent_Prototype_Architecture.pdf), sections 3 and 8. Diagrams: [Figure 5](source/diagrams/figure_05.png) (visitor tools), [Figure 6](source/diagrams/figure_06.png) (back-office tools).

Tool schemas, implementations and the allowlist per project live in `tools.py`. The allowlist comes from config (Fig. 2). A tool request that is not on the allowlist, or whose input does not match its schema, returns an error to the model and has no side effects (PDF section 3).

## Tool table

| Tool | Role | Input | Side effect | Notes |
|------|------|-------|-------------|-------|
| `search_kb` | Visitor chat | `query` | none | Returns approved entries with IDs |
| `get_price_sheet` | Visitor chat | `plan` | none | Only source of prices |
| `handoff_to_sales` | Visitor chat | `summary` | `handoffs` row | Used when the KB has no answer |
| `get_listing` | Back-office | `listing_id` | none | Reads mock PMS data |
| `get_reservation` | Back-office | `reservation_id` | none | Payment details masked |
| `run_parity_check` | Back-office | `listing_id`, `start`, `end` | `gaps` rows | Never changes rates |
| `list_gaps` | Back-office | `listing_id` | none | Open gaps only |
| `propose_change` | Back-office | `type`, `target`, `before`, `after` | `changes` row (pending) | Rejects stale before values |
| `get_change_status` | Back-office | `change_id` | none | Shows state history |
| `handoff_to_human` | Back-office | `reason` | `handoffs` row | Used when staff need a person |

There is no messaging tool for either role. Guest messaging is refused before the model runs, and the refusal is logged.

## Per-tool notes

### search_kb (Visitor chat)
Returns approved entries with IDs. Replies must cite `[kb:ID]` of an approved entry or stage 6 replaces them with a hand-off offer (Fig. 5). [ASSUMPTION: the retrieval threshold is a default not given in the PDF.] (A-04)

### get_price_sheet (Visitor chat)
Only source of prices. The project owner edits the price sheet (Fig. 1). [ASSUMPTION: the PDF does not say where the price sheet file lives or how a price answer satisfies the stage 6 `[kb:ID]` citation check.] (A-17)

### handoff_to_sales (Visitor chat)
Writes a `handoffs` row (session_id, reason, summary, created_at; Fig. 4). Used when the KB has no answer.

### get_listing (Back-office)
Read-only. Reads mock PMS data.

### get_reservation (Back-office)
Read-only. Payment details, where they appear in mock reservations, are masked to the last four digits in every output and log (PDF section 5).

### run_parity_check (Back-office)
Write tool (limited): writes gap rows only. Never changes rates. Same flow as `POST /api/parity/run` ([Figure 7](source/diagrams/figure_07.png)), implemented by `parity.py`.

### list_gaps (Back-office)
Read-only. Open gaps only.

### propose_change (Back-office)
Write tool (limited): writes a pending row only and checks the before value is current. Rejects stale before values (state `rejected_at_proposal`). Implemented through `changes.py` ("propose only", Fig. 2). It cannot approve or apply a change.

### get_change_status (Back-office)
Read-only. Shows state history.

### handoff_to_human (Back-office)
Write tool (limited): writes a handoff row. Used when staff need a person.

## Classification (Figure 6)

| Read-only tools (no side effects) | Write tools (limited) |
|-----------------------------------|-----------------------|
| `get_listing`, `get_reservation`, `list_gaps`, `get_change_status` | `run_parity_check`, `propose_change`, `handoff_to_human` |

## Related documents

- Pipelines that call these tools: [AI_PIPELINE.md](AI_PIPELINE.md)
- Endpoints with the same effects: [API.md](API.md)
