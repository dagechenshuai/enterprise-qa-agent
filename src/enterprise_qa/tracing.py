"""逐事件持久化、运行身份与证据文件。"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def json_text(value: object) -> str:
    """统一 UTF-8 JSON，额外移除意外出现的凭据。"""
    text = json.dumps(value, ensure_ascii=False, indent=2)
    key = os.getenv("MODEL_API_KEY")
    if key:
        text = text.replace(key, "[REDACTED]")
    return re.sub(r"sk-[A-Za-z0-9_-]{16,}", "[REDACTED]", text)


def write_json(path: Path, value: object) -> None:
    """写入可审阅 JSON 文件。"""
    path.write_text(json_text(value) + "\n", encoding="utf-8")


class Trace:
    """独占新运行目录，拒绝覆盖既有运行证据。"""

    def __init__(self, directory: Path, mode: str, model: str, dataset: str) -> None:
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.common = {
            "run_id": uuid4().hex,
            "mode": mode,
            "model": model,
            "dataset": dataset,
        }
        self.step = 0

    def event(self, kind: str, **fields: object) -> None:
        """同步追加事件，异常发生前的成功观察也能保留。"""
        self.step += 1
        record = {
            **self.common,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": self.step,
            "event": kind,
            **fields,
        }
        with (self.directory / "trace.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(json.loads(json_text(record)), ensure_ascii=False) + "\n"
            )
