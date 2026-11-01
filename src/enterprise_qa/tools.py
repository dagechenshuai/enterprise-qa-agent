"""可观察的工具执行、参数校验与可复现故障注入。"""

from collections import Counter

from pydantic import ValidationError

from enterprise_qa.retrieval import Corpus
from enterprise_qa.schemas import ReadArgs, SearchArgs

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "检索合成企业制度，返回候选与摘要。空结果可换词补查；摘要不能代替读取原文。",
            "parameters": SearchArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "读取指定文档全部片段及适用范围。引用必须来自本次读取成功的原文。",
            "parameters": ReadArgs.model_json_schema(),
        },
    },
]


class ToolExecutor:
    """每次问答独立保存调用计数和成功读取证据。"""

    def __init__(
        self, corpus: Corpus, failures: dict[str, list[int]] | None = None
    ) -> None:
        self.corpus = corpus
        self.failures = failures or {}
        if set(self.failures) - {"search_documents", "read_document"}:
            raise ValueError("故障配置包含未知工具")
        self.calls: Counter = Counter()
        self.read_documents: dict[str, dict] = {}

    def execute(self, name: str, arguments: str) -> dict:
        """错误作为观察结果返回，不隐藏失败或替模型重试。"""
        self.calls[name] += 1
        if name not in {"search_documents", "read_document"}:
            return {"ok": False, "error": "unknown_tool"}
        try:
            schema = SearchArgs if name == "search_documents" else ReadArgs
            args = schema.model_validate_json(arguments)
        except (ValueError, ValidationError):
            return {
                "ok": False,
                "error": "invalid_arguments",
                "schema": schema.model_json_schema(),
            }
        if self.calls[name] in self.failures.get(name, []):
            return {"ok": False, "error": "injected_tool_failure", "retryable": True}
        if isinstance(args, SearchArgs):
            return {"ok": True, "results": self.corpus.search(args.query, args.top_k)}
        document = self.corpus.documents.get(args.document_id)
        if document is None:
            return {"ok": False, "error": "document_not_found", "retryable": False}
        result = document.model_dump()
        self.read_documents[args.document_id] = result
        return {"ok": True, "document": result}
