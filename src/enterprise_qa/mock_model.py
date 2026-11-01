"""离线规则替身：仅证明流程，不能作为真实模型决策证据。"""

import json
import re
from uuid import uuid4

from enterprise_qa.models import ModelReply
from enterprise_qa.schemas import Answer
from enterprise_qa.validation import evidence_citations


def tool_reply(name: str, arguments: dict, note: str) -> ModelReply:
    """构建符合真实工具协议的测试消息。"""
    return ModelReply(
        {
            "role": "assistant",
            "content": note,
            "tool_calls": [
                {
                    "id": "mock_" + uuid4().hex,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            ],
        }
    )


class MockModel:
    """根据观察执行有限规则；所有说明均标明 Mock。"""

    mode = "mock"
    name = "offline-rule-double"

    def respond(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        """演示查询、读取、错误后重试和最终结果，不模拟真实智能。"""
        observations = [
            json.loads(msg["content"]) for msg in messages if msg["role"] == "tool"
        ]
        if not observations:
            questions = [msg["content"] for msg in messages if msg["role"] == "user"]
            return tool_reply(
                "search_documents",
                {"query": " ".join(questions)[-500:], "top_k": 5},
                "Mock：按输入检索。",
            )
        if not observations[-1].get("ok"):
            previous = next(msg for msg in reversed(messages) if msg.get("tool_calls"))
            call = previous["tool_calls"][0]["function"]
            return tool_reply(
                call["name"],
                json.loads(call["arguments"]),
                "Mock：观察到错误后重试，受执行上限约束。",
            )
        documents = {
            obs["document"]["document_id"]: obs["document"]
            for obs in observations
            if "document" in obs
        }
        searches = [obs["results"] for obs in observations if "results" in obs]
        candidates = searches[0] if searches else []
        if candidates:
            for candidate in candidates:
                if (
                    candidate["score"] == candidates[0]["score"]
                    and candidate["document_id"] not in documents
                ):
                    return tool_reply(
                        "read_document",
                        {"document_id": candidate["document_id"]},
                        "Mock：读取最高分候选原文。",
                    )
        return self._final(documents, len(searches))

    def _final(self, documents: dict[str, dict], search_count: int) -> ModelReply:
        citations = evidence_citations(documents)
        texts = [citation.quote for citation in citations]
        # 此处故意是简单离线规则；仅能识别同标题、不同天数的模拟冲突。
        titles = {doc["title"] for doc in documents.values()}
        numbers = {number for text in texts for number in re.findall(r"\d+\s*天", text)}
        conflict = len(documents) > 1 and len(titles) == 1 and len(numbers) > 1
        if conflict and search_count == 1:
            return tool_reply(
                "search_documents",
                {"query": " ".join(titles) + " 适用范围 优先级 替代", "top_k": 5},
                "Mock：补查同主题制度适用依据。",
            )
        status = (
            "needs_clarification"
            if conflict
            else "answered" if texts else "insufficient_evidence"
        )
        answer = Answer(
            status=status,
            answer="\n".join(texts) or "资料中未找到依据。",
            citations=citations,
            gaps=["适用范围或优先级"] if conflict else [] if texts else ["相关制度"],
            conflicts=["同主题制度存在不同期限"] if conflict else [],
            follow_up_question="请确认适用制度。" if conflict else None,
            reason="离线规则替身输出，不证明真实模型决策能力。",
        )
        return ModelReply({"role": "assistant", "content": answer.model_dump_json()})
