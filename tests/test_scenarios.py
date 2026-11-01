"""完整离线场景和 CLI 检查，绝不代表真实模型效果。"""

import json
from pathlib import Path

import pytest

from enterprise_qa.cli import main
from enterprise_qa.evaluation import assess, evaluate
from enterprise_qa.runtime import run_question
from enterprise_qa.schemas import Budget, Question

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "data/scenarios.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_mock_acceptance(case: dict, tmp_path) -> None:
    budget = Budget(max_tool_calls=case.get("max_tool_calls", 8))
    result = run_question(
        Question(question=case["question"], history=case.get("history", [])),
        ROOT / "data" / case["dataset"],
        tmp_path / "run",
        "mock",
        budget,
        case.get("failures"),
    )
    events = [
        json.loads(line)
        for line in (tmp_path / "run/trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assessment = assess(case, result, events, budget)
    assert assessment["passed"], assessment


def test_cli_mock_exit(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "enterprise-qa",
            "ask",
            "报销期限",
            "--mode",
            "mock",
            "--dataset",
            str(ROOT / "data/normal.json"),
            "--output",
            str(tmp_path / "run"),
        ],
    )
    assert main() == 0
    assert (tmp_path / "run/output.json").exists()


def test_cli_invalid_input(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "enterprise-qa",
            "ask",
            " ",
            "--mode",
            "mock",
            "--output",
            str(tmp_path / "run"),
        ],
    )
    assert main() == 2


def test_real_evaluation_missing_config_is_reported(monkeypatch, tmp_path) -> None:
    """真实配置缺失不能降级为离线成功，也不能继续刷请求。"""
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    output = tmp_path / "batch"
    assert evaluate(ROOT / "data/scenarios.json", output, "real", 1.0) == 1
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert report["aborted_reason"] == "missing_model_configuration"
    assert len(report["not_run"]) == 7
    assert report["cases"][0]["status"] == "incomplete"


def test_mock_batch_is_reproducible(tmp_path) -> None:
    output = tmp_path / "batch"
    assert evaluate(ROOT / "data/scenarios.json", output, "mock", 1.0) == 0
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert len(report["cases"]) == 8
    assert all(case["passed"] for case in report["cases"])


def test_wrong_answer_with_correct_quote_fails_assessment(tmp_path) -> None:
    """真实引文存在，也不能把错误答案判为通过。"""
    case = CASES[0]
    result = run_question(
        Question(question=case["question"]),
        ROOT / "data/normal.json",
        tmp_path / "run",
        "mock",
        Budget(),
    )
    result.answer = "报销期限是 99 天。"
    events = [
        json.loads(line)
        for line in (tmp_path / "run/trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assessment = assess(case, result, events, Budget())
    assert not assessment["passed"]
    assert assessment["checks"]["quote_facts"]
    assert not assessment["checks"]["answer_facts"]
