"""独立测试夹具，不访问真实模型。"""

from pathlib import Path

import pytest

from enterprise_qa.retrieval import Corpus

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def corpus() -> Corpus:
    """使用正常合成资料。"""
    return Corpus(ROOT / "data/normal.json")
