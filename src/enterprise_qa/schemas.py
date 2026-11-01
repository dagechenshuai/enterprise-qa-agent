"""资料、消息、工具参数与结果约束。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """拒绝意外字段和隐式类型转换。"""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Chunk(StrictModel):
    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Document(StrictModel):
    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    version_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    scope: str | None
    chunks: list[Chunk] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_chunks(self) -> "Document":
        """片段 ID 在文档内唯一。"""
        if len({chunk.chunk_id for chunk in self.chunks}) != len(self.chunks):
            raise ValueError("片段 ID 重复")
        return self


class HistoryMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class Question(StrictModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)


class Citation(StrictModel):
    document_id: str
    version_date: str
    chunk_id: str
    quote: str = Field(min_length=1)


class Answer(StrictModel):
    status: Literal[
        "answered", "needs_clarification", "insufficient_evidence", "incomplete"
    ]
    answer: str
    citations: list[Citation]
    gaps: list[str]
    conflicts: list[str]
    follow_up_question: str | None
    reason: str

    @model_validator(mode="after")
    def consistent_status(self) -> "Answer":
        """成功需要证据；未完成与澄清状态需要具体原因。"""
        if self.status == "answered":
            if not self.answer or not self.citations or self.conflicts or self.gaps:
                raise ValueError("answered 需要答案与引用，且不能存在未解决冲突或缺口")
        if self.status == "needs_clarification" and not self.follow_up_question:
            raise ValueError("澄清状态必须提供追问")
        if self.status != "answered" and not self.reason:
            raise ValueError("非成功状态必须说明原因")
        return self


class SearchArgs(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)


class ReadArgs(StrictModel):
    document_id: str = Field(min_length=1, max_length=100)


class Budget(StrictModel):
    max_model_turns: int = Field(default=10, ge=1, le=30)
    max_tool_calls: int = Field(default=8, ge=1, le=30)
    timeout_seconds: float = Field(default=60.0, gt=0, le=180)
