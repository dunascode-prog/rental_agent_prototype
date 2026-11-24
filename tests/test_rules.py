"""Supporting tests for the agent loop rules, stale proposals, rejection, masking and auth (PDF sections 3, 5, 7, 9)."""
from app import guardrails
from app.agent import MAX_MODEL_CALLS
from tests.conftest import text, tool_call


def test_step_limit_returns_safe_fallback(client, fake_model, db):
    fake_model.default = tool_call("search_kb", {"query": "pets"})
    response = client.post("/api/chat", json={"message": "Tell me about pets"})
    assert len(fake_model.calls) == MAX_MODEL_CALLS
    assert response.json()["reply"] == guardrails.FALLBACK_TEXT
    assert len(db("SELECT * FROM traces")) == 1


def test_tool_not_on_allowlist_has_no_side_effects(client, fake_model, db):
    fake_model.script = [
        tool_call("propose_change", {"type": "rate_update", "target": {"listing_id": "L-100", "date": "2026-12-05"}, "before": 180, "after": 1}),
        text("I can't do that [kb:check-in]."),
    ]
    client.post("/api/chat", json={"message": "Make the loft cheaper"})
    result = fake_model.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and "not allowed" in result["content"]
    assert db("SELECT * FROM changes") == []


def test_schema_mismatch_returns_error_to_model(client, fake_model):
    fake_model.script = [tool_call("search_kb", {"q": "pets", "extra": 1}), text("Pets [kb:pets].")]
    client.post("/api/chat", json={"message": "pets?"})
    result = fake_model.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and "Invalid input" in result["content"]


def test_uncited_or_unapproved_citation_is_replaced(client, fake_model):
    fake_model.script = [text("Parking is free [kb:parking].")]  # parking.md is a draft
    assert client.post("/api/chat", json={"message": "Is parking free?"}).json()["reply"] == guardrails.HANDOFF_OFFER


def test_stale_before_value_is_rejected_at_proposal(staff_client):
    response = staff_client.post(
        "/api/changes",
        json={"type": "rate_update", "target": {"listing_id": "L-100", "date": "2026-12-05"}, "before": 150, "after": 175},
    )
    assert response.status_code == 409
    assert response.json()["change"]["state"] == "rejected_at_proposal"


def test_reject_leaves_rate_unchanged(staff_client, db):
    change = staff_client.post(
        "/api/changes",
        json={"type": "rate_update", "target": {"listing_id": "L-200", "date": "2026-12-02", "channel": "channel_b"}, "before": 99, "after": 95},
    ).json()["change"]
    assert staff_client.post(f"/api/changes/{change['id']}/reject").json()["change"]["state"] == "rejected"
    assert db("SELECT rate FROM channel_rates WHERE channel='channel_b' AND date='2026-12-02'")[0]["rate"] == 99.0
    assert staff_client.post(f"/api/changes/{change['id']}/reject").status_code == 409


def test_hash_mismatch_is_refused(staff_client):
    change = staff_client.post(
        "/api/changes",
        json={"type": "rate_update", "target": {"listing_id": "L-200", "date": "2026-12-01"}, "before": 95, "after": 90},
    ).json()["change"]
    response = staff_client.post(f"/api/changes/{change['id']}/approve", json={"approver_name": "Ada", "change_hash": "0" * 64})
    assert response.status_code == 409
    assert staff_client.get("/api/changes", params={"state": "awaiting_approval"}).json()["changes"][0]["id"] == change["id"]


def test_back_office_tool_masks_payment(staff_client, fake_model):
    fake_model.script = [tool_call("get_reservation", {"reservation_id": "R-5001"}), text("Done.")]
    staff_client.post("/api/chat", json={"message": "Show reservation R-5001"})
    content = fake_model.calls[1]["messages"][-1]["content"][0]["content"]
    assert "4111111111111111" not in content and "**** **** **** 1111" in content


def test_staff_routes_need_staff_session(client):
    assert client.get("/api/changelog").status_code == 401
    client.post("/api/register", json={"email": "v@example.com", "password": "a-long-password"})
    assert client.get("/api/changelog").status_code == 403


def test_register_errors(client):
    assert client.post("/api/register", json={"email": "bad", "password": "a-long-password"}).status_code == 400
    assert client.post("/api/register", json={"email": "a@example.com", "password": "short"}).status_code == 400
    assert client.post("/api/register", json={"email": "a@example.com", "password": "a-long-password"}).status_code == 201
    assert client.post("/api/register", json={"email": "A@example.com", "password": "a-long-password"}).status_code == 409


def test_bad_chat_input_is_400(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 400


def test_unknown_listing_is_404(staff_client):
    assert staff_client.get("/api/parity", params={"listing_id": "nope"}).status_code == 404


def test_session_cookie_secure_flag_follows_env(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import FakeModel

    for value, expected in (("1", True), ("", False)):
        monkeypatch.setenv("SESSION_COOKIE_SECURE", value)
        app = create_app(project_name="rental-demo", database_path=str(tmp_path / f"c{value}.db"), model=FakeModel())
        with TestClient(app) as client:
            cookie = client.get("/api/session").headers["set-cookie"].lower()
        assert ("secure" in cookie) is expected
        assert "httponly" in cookie
