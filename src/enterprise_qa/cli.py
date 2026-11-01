"""命令行问答与批量场景评估。"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from enterprise_qa.runtime import run_question
from enterprise_qa.schemas import Budget, Question
from enterprise_qa.tracing import json_text


def parser() -> argparse.ArgumentParser:
    """定义可复制的问答和评估命令。"""
    root = argparse.ArgumentParser(description="企业制度问答 Agent")
    commands = root.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask", help="运行一次问答")
    ask.add_argument("question")
    ask.add_argument("--dataset", type=Path, default=Path("data/normal.json"))
    ask.add_argument("--history", type=Path, help="仅 user/assistant 消息的 JSON 数组")
    ask.add_argument("--output", type=Path)
    ask.add_argument("--fail-first-read", action="store_true")
    ask.add_argument("--max-tool-calls", type=int, default=8)
    ask.add_argument("--max-model-turns", type=int, default=10)
    evaluate = commands.add_parser("evaluate", help="执行八个验收场景")
    evaluate.add_argument("--cases", type=Path, default=Path("data/scenarios.json"))
    evaluate.add_argument("--output", type=Path)
    for command in (ask, evaluate):
        command.add_argument("--mode", choices=["real", "mock"], default="real")
        command.add_argument("--timeout", type=float, default=60.0)
    return root


def main() -> int:
    """只加载当前目录 .env，避免意外读取外层项目凭据。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(Path.cwd() / ".env", override=False)
    args = parser().parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output or Path("runs") / args.mode / stamp
    try:
        if args.command == "evaluate":
            from enterprise_qa.evaluation import evaluate

            return evaluate(args.cases, output, args.mode, args.timeout)
        history = (
            json.loads(args.history.read_text(encoding="utf-8-sig"))
            if args.history
            else []
        )
        question = Question(question=args.question, history=history)
        budget = Budget(
            max_tool_calls=args.max_tool_calls,
            max_model_turns=args.max_model_turns,
            timeout_seconds=args.timeout,
        )
        result = run_question(
            question,
            args.dataset,
            output,
            args.mode,
            budget,
            {"read_document": [1]} if args.fail_first_read else None,
        )
        print(
            json_text({"output_directory": str(output), "result": result.model_dump()})
        )
        return 2 if result.status == "incomplete" else 0
    except (OSError, ValueError, ValidationError) as exc:
        # 不回显异常全文，防止配置或用户输入随 traceback 泄露。
        print(
            json_text(
                {
                    "error": type(exc).__name__,
                    "message": "检查输入、资料和输出目录；目录必须不存在。",
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
