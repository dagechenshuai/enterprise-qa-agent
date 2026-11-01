"""组合资料、模型、执行器及持久化入口。"""

import hashlib
import platform
from importlib.metadata import version
from pathlib import Path

from enterprise_qa.agent import Agent
from enterprise_qa.mock_model import MockModel
from enterprise_qa.models import RealModel
from enterprise_qa.retrieval import Corpus
from enterprise_qa.schemas import Answer, Budget, Question
from enterprise_qa.tools import ToolExecutor
from enterprise_qa.tracing import Trace, write_json


def run_question(
    question: Question,
    dataset: Path,
    output: Path,
    mode: str,
    budget: Budget,
    failures: dict[str, list[int]] | None = None,
) -> Answer:
    """创建独立问答实例，记录可重放输入与资料快照。"""
    if mode not in {"real", "mock"}:
        raise ValueError("运行模式只能是 real 或 mock")
    corpus = Corpus(dataset)
    model = RealModel(budget.timeout_seconds) if mode == "real" else MockModel()
    executor = ToolExecutor(corpus, failures)
    trace = Trace(output, model.mode, model.name, corpus.name)
    write_json(
        output / "manifest.json",
        {
            "python": platform.python_version(),
            "mode": mode,
            "model": model.name,
            "dependencies": {
                name: version(name)
                for name in ("httpx", "pydantic", "jieba", "python-dotenv")
            },
            "source_sha256": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(Path(__file__).parent.glob("*.py"))
            },
        },
    )
    write_json(
        output / "input.json",
        {
            **question.model_dump(),
            "mode": mode,
            "dataset": dataset.name,
            "corpus_sha256": corpus.digest,
            "budget": budget.model_dump(),
            "failures": failures or {},
        },
    )
    write_json(
        output / "corpus.json", [doc.model_dump() for doc in corpus.documents.values()]
    )
    return Agent(model, executor, budget, trace).run(question)
