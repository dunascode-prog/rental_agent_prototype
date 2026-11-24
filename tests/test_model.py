"""Tests for the Bedrock request built by model.py (no network) and cache-aware token counting."""
from types import SimpleNamespace

import pytest

from app.model import BedrockModel, ModelError
from tests.conftest import text


def _capturing_model() -> tuple[BedrockModel, list[dict]]:
    sent: list[dict] = []
    model = BedrockModel(region="test-region")
    model._client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: sent.append(kw) or text("ok")))
    return model, sent


def _complete(model: BedrockModel, cache: bool) -> None:
    model.complete(
        model_id="us.anthropic.test-model-v1:0",
        system="SYSTEM PROMPT",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        max_tokens=100,
        cache=cache,
    )


def test_cache_on_marks_system_prompt_and_last_message():
    model, sent = _capturing_model()
    _complete(model, cache=True)
    request = sent[0]
    assert request["system"] == [{"type": "text", "text": "SYSTEM PROMPT", "cache_control": {"type": "ephemeral"}}]
    assert request["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "hi", "cache_control": {"type": "ephemeral"}}]}
    ]
    assert "cache_control" not in request  # InvokeModel rejects top-level cache_control


def test_cache_marks_last_tool_result_without_changing_the_callers_messages():
    model, sent = _capturing_model()
    results = [{"type": "tool_result", "tool_use_id": "t1", "content": "a"},
               {"type": "tool_result", "tool_use_id": "t2", "content": "b"}]
    messages = [{"role": "user", "content": "hi"}, {"role": "user", "content": results}]
    model.complete(model_id="m", system="s", messages=messages, tools=[], max_tokens=10, cache=True)
    sent_blocks = sent[0]["messages"][-1]["content"]
    assert sent_blocks[0] == results[0]
    assert sent_blocks[1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in results[1]
    assert sent[0]["messages"][0] == {"role": "user", "content": "hi"}


def test_cache_off_sends_plain_request():
    model, sent = _capturing_model()
    _complete(model, cache=False)
    assert sent[0]["system"] == "SYSTEM PROMPT"
    assert sent[0]["messages"] == [{"role": "user", "content": "hi"}]
    assert "cache_control" not in sent[0]


def test_placeholder_model_id_is_refused():
    model, sent = _capturing_model()
    with pytest.raises(ModelError):
        model.complete(model_id="<bedrock-model-id>", system="s", messages=[], tools=[], max_tokens=10)
    assert sent == []


def test_agent_passes_cache_flag_and_counts_cached_tokens(client, fake_model, db):
    reply = text("Check-in is from 3 pm [kb:check-in].")
    reply.usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=900, cache_creation_input_tokens=100)
    fake_model.script = [reply]
    client.post("/api/chat", json={"message": "When is check-in?"})
    assert fake_model.calls[0]["cache"] is True
    trace = db("SELECT input_tokens, output_tokens FROM traces")[0]
    assert (trace["input_tokens"], trace["output_tokens"]) == (1010, 5)


def test_model_ids_fall_back_to_env_when_config_has_placeholders(monkeypatch):
    from app.config import BACKOFFICE_ROLE, VISITOR_ROLE, load_project_config

    monkeypatch.setenv("BEDROCK_MODEL_CHAT", "chat-model-from-env")
    monkeypatch.setenv("BEDROCK_MODEL_BACKOFFICE", "backoffice-model-from-env")
    project = load_project_config("rental-demo")
    assert project.models == {VISITOR_ROLE: "chat-model-from-env", BACKOFFICE_ROLE: "backoffice-model-from-env"}


def test_model_ids_stay_placeholders_without_env(monkeypatch):
    from app.config import VISITOR_ROLE, is_placeholder, load_project_config

    monkeypatch.delenv("BEDROCK_MODEL_CHAT", raising=False)
    assert is_placeholder(load_project_config("rental-demo").models[VISITOR_ROLE])
