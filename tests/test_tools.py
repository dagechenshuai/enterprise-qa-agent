"""检索、故障注入和参数边界的行为测试。"""

import json

import pytest

from enterprise_qa.retrieval import Corpus
from enterprise_qa.tools import ToolExecutor


@pytest.mark.parametrize(
    "query", ["报销要在几天内提交", "出差回来多久得把票交上去报账"]
)
def test_similar_query(corpus: Corpus, query: str) -> None:
    results = corpus.search(query, 5)
    assert results[0]["document_id"] == "D01"


def test_outside_question(corpus: Corpus) -> None:
    assert corpus.search("公司明年会涨薪多少", 5) == []


@pytest.mark.parametrize(
    "arguments",
    [
        '{"query":""}',
        '{"query":"报销","top_k":0}',
        '{"query":"报销","top_k":"5"}',
        '{"query":"报销","extra":true}',
        "[]",
        "not-json",
    ],
)
def test_invalid_arguments(corpus: Corpus, arguments: str) -> None:
    executor = ToolExecutor(corpus)
    result = executor.execute("search_documents", arguments)
    assert result["error"] == "invalid_arguments"


def test_failed_read_is_not_evidence(corpus: Corpus) -> None:
    executor = ToolExecutor(corpus, {"read_document": [1]})
    first = executor.execute("read_document", '{"document_id":"D01"}')
    assert not first["ok"]
    assert not executor.read_documents
    second = executor.execute("read_document", '{"document_id":"D01"}')
    assert second["ok"]
    assert "D01" in executor.read_documents


def test_unknown_and_missing_document(corpus: Corpus) -> None:
    executor = ToolExecutor(corpus)
    assert executor.execute("delete_documents", "{}")["error"] == "unknown_tool"
    assert (
        executor.execute("read_document", '{"document_id":"missing"}')["error"]
        == "document_not_found"
    )


def test_duplicate_document_rejected(tmp_path, corpus: Corpus) -> None:
    data = [corpus.documents["D01"].model_dump()] * 2
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="文档 ID 重复"):
        Corpus(path)
