"""HTTP 协议测试：不连接真实模型，不记录凭据。"""

import json

import httpx
import pytest

from enterprise_qa.models import ModelError, RealModel, normalize_message
from enterprise_qa.tracing import Trace, write_json


@pytest.fixture
def config(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "test-private-key")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("MODEL_BASE_URL", "https://api.deepseek.com")


def test_http_protocol_and_reasoning_exclusion(config) -> None:
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "test",
                "model": "served",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": "读取原文",
                            "reasoning_content": "不记录的内部字段",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_document",
                                        "arguments": '{"document_id":"D01"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    result = RealModel(transport=httpx.MockTransport(handler)).respond(
        [{"role": "user", "content": "问题"}], []
    )
    assert captured[0]["thinking"] == {"type": "disabled"}
    assert result.message["tool_calls"][0]["id"] == "call-1"
    assert "reasoning_content" not in result.message
    assert result.metadata["served_model"] == "served"


@pytest.mark.parametrize("status", [400, 401, 402, 429, 500])
def test_http_error_is_safe(config, status: int) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, text="test-private-key")
    )
    with pytest.raises(ModelError, match=f"^model_http_{status}$"):
        RealModel(transport=transport).respond([], [])


def test_timeout(config) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret transport error")

    with pytest.raises(ModelError, match="^model_timeout$"):
        RealModel(transport=httpx.MockTransport(handler)).respond([], [])


def test_missing_configuration(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(ModelError, match="missing_model_configuration"):
        RealModel().respond([], [])


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"choices": []},
        {"choices": [{"message": None}]},
        {"choices": [{"finish_reason": "length"}]},
    ],
)
def test_malformed_response(config, body: dict) -> None:
    with pytest.raises(ModelError):
        RealModel(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=body)
            )
        ).respond([], [])


def test_duplicate_call_ids_rejected() -> None:
    call = {
        "id": "same",
        "type": "function",
        "function": {"name": "read_document", "arguments": "{}"},
    }
    with pytest.raises(ModelError):
        normalize_message({"role": "assistant", "tool_calls": [call, call]})


def test_trace_redacts_and_refuses_overwrite(tmp_path, config) -> None:
    trace = Trace(tmp_path / "run", "mock", "test", "normal")
    trace.event("test", message="test-private-key")
    write_json(tmp_path / "output.json", {"secret": "test-private-key"})
    assert "test-private-key" not in (tmp_path / "run/trace.jsonl").read_text()
    assert "test-private-key" not in (tmp_path / "output.json").read_text()
    with pytest.raises(FileExistsError):
        Trace(tmp_path / "run", "mock", "test", "normal")
