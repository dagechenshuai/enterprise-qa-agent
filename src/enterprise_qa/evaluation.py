"""场景自动断言与人工语义复核分开报告。"""

import json
import re
from pathlib import Path

from enterprise_qa.runtime import run_question
from enterprise_qa.schemas import Answer, Budget, Question
from enterprise_qa.tracing import write_json


def assess(case: dict, answer: Answer, events: list[dict], budget: Budget) -> dict:
    """断言可机械核验的属性；不把关键词断言称为语义验收。"""
    quotes = "\n".join(citation.quote for citation in answer.citations)
    ids = {citation.document_id for citation in answer.citations}
    tools = [event for event in events if event["event"] == "tool_result"]
    checks = {
        "status": answer.status in case["statuses"],
        "tool_budget": len(tools) <= budget.max_tool_calls,
        "required_citations": set(case.get("required_ids", [])) <= ids,
        "quote_facts": all(term in quotes for term in case.get("quote_contains", [])),
        "answer_facts": all(
            re.search(pattern, answer.answer)
            for pattern in case.get("answer_patterns", [])
        ),
        "observed_tool": bool(tools),
    }
    if case.get("no_citations"):
        checks["no_unsupported_citations"] = not answer.citations
    if case.get("check_conflict"):
        checks["conflict_and_question"] = bool(
            answer.conflicts and answer.follow_up_question
        )
        reads = [
            index
            for index, event in enumerate(tools)
            if event["tool"] == "read_document" and event["result"].get("ok")
        ]
        checks["investigated_conflict"] = len(reads) >= 2 and any(
            event["tool"] == "search_documents" for event in tools[reads[1] + 1 :]
        )
    if case.get("require_failure"):
        failures = [
            index
            for index, event in enumerate(events)
            if event["event"] == "tool_result" and not event["result"].get("ok")
        ]
        checks["failure_observed"] = bool(failures)
        checks["model_acted_after_failure"] = bool(failures) and any(
            event["event"] == "model_response" for event in events[failures[0] + 1 :]
        )
        if answer.status == "answered":
            checks["recovered_evidence"] = (
                "D01" in ids
                and "30" in quotes
                and bool(re.search(r"30\s*天", answer.answer))
            )
    if case.get("reason"):
        checks["stop_reason"] = answer.reason == case["reason"]
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "status": answer.status,
        "tool_calls": len(tools),
        "semantic_review": "pending",
    }


def evaluate(cases_path: Path, output: Path, mode: str, timeout: float) -> int:
    """顺序执行场景，逐例保存结果，任何失败均返回非零退出码。"""
    cases = json.loads(cases_path.read_text(encoding="utf-8-sig"))
    output.mkdir(parents=True, exist_ok=False)
    report = {"mode": mode, "meaning": "自动属性断言；语义需另行复核", "cases": []}
    for case in cases:
        directory = output / case["id"]
        budget = Budget(
            max_tool_calls=case.get("max_tool_calls", 8), timeout_seconds=timeout
        )
        answer = run_question(
            Question(question=case["question"], history=case.get("history", [])),
            cases_path.parent / case["dataset"],
            directory,
            mode,
            budget,
            case.get("failures"),
        )
        events = [
            json.loads(line)
            for line in (directory / "trace.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assessment = assess(case, answer, events, budget)
        write_json(directory / "assessment.json", assessment)
        report["cases"].append({"id": case["id"], **assessment})
        write_json(output / "summary.json", report)
        print(
            f"{case['id']}: {answer.status}, 自动断言={'通过' if assessment['passed'] else '失败'}",
            flush=True,
        )
        if mode == "real" and answer.reason in {
            "missing_model_configuration",
            "model_http_401",
            "model_http_402",
        }:
            report["aborted_reason"] = answer.reason
            report["not_run"] = [
                remaining["id"] for remaining in cases[len(report["cases"]) :]
            ]
            write_json(output / "summary.json", report)
            return 1
    return 0 if all(case["passed"] for case in report["cases"]) else 1
