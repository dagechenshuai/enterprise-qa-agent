"""真实模型 HTTP 适配，保留工具协议，不记录内部思维字段。"""

import os
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

import httpx


class ModelError(Exception):
    """对外只暴露无凭据的错误码。"""


@dataclass
class ModelReply:
    """模型消息及可公开的响应元信息。"""

    message: dict
    metadata: dict = field(default_factory=dict)


class Model(Protocol):
    """真实模型和测试替身共用的接口。"""

    mode: str
    name: str

    def respond(self, messages: list[dict], tools: list[dict]) -> ModelReply: ...


def normalize_message(message: dict) -> dict:
    """白名单提取普通消息，忽略 reasoning_content 等内部推理字段。"""
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ModelError("invalid_assistant_message")
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise ModelError("invalid_content")
    normalized = {"role": "assistant", "content": content}
    calls = message.get("tool_calls") or []
    if not isinstance(calls, list):
        raise ModelError("invalid_tool_calls")
    seen_ids = set()
    for call in calls:
        try:
            valid = (
                call["type"] == "function"
                and isinstance(call["id"], str)
                and bool(call["id"])
                and call["id"] not in seen_ids
                and isinstance(call["function"]["name"], str)
                and isinstance(call["function"]["arguments"], str)
            )
            if not valid:
                raise ValueError
            seen_ids.add(call["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelError("invalid_tool_call") from exc
    if calls:
        normalized["tool_calls"] = [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["function"]["name"],
                    "arguments": call["function"]["arguments"],
                },
            }
            for call in calls
        ]
    return normalized


class RealModel:
    """调用非流式 Chat Completions，不做隐藏重试或 Mock 降级。"""

    mode = "real"

    def __init__(
        self, timeout: float = 60.0, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.name = os.getenv("MODEL_NAME", "").strip()
        self.key = os.getenv("MODEL_API_KEY", "").strip()
        self.base_url = os.getenv("MODEL_BASE_URL", "").strip().rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def respond(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        """校验配置、发送请求，并返回经过白名单筛选的模型消息。"""
        if not all((self.name, self.key, self.base_url)):
            raise ModelError("missing_model_configuration")
        parsed = urlparse(self.base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ModelError("invalid_https_base_url")
        payload = {
            "model": self.name,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
            "max_tokens": 2500,
        }
        if parsed.hostname == "api.deepseek.com":
            payload["thinking"] = {"type": "disabled"}
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(
                    self.base_url + "/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.key}"},
                )
            if response.status_code != 200:
                raise ModelError(f"model_http_{response.status_code}")
            data = response.json()
            choice = data["choices"][0]
            if choice.get("finish_reason") in {"length", "content_filter"}:
                raise ModelError("model_output_" + choice["finish_reason"])
            return ModelReply(
                normalize_message(choice["message"]),
                {
                    "response_id": data.get("id"),
                    "served_model": data.get("model"),
                    "usage": data.get("usage"),
                    "finish_reason": choice.get("finish_reason"),
                },
            )
        except httpx.TimeoutException as exc:
            raise ModelError("model_timeout") from exc
        except httpx.RequestError as exc:
            raise ModelError("model_connection_error") from exc
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ModelError("invalid_model_response") from exc
