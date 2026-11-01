"""本地小规模中文关键词检索，不承担答案决策。"""

import hashlib
import json
import logging
import re
from pathlib import Path

import jieba

from enterprise_qa.schemas import Document

jieba.setLogLevel(logging.ERROR)
STOP_WORDS = set(
    "的 了 吗 呢 是 在 要 我 公司 员工 规定 制度 如何 什么 多少 多久 可以 一样 也".split()
)
SYNONYMS = {
    "出差": "差旅",
    "票据": "报销",
    "交票": "报销",
    "报账": "报销",
    "休假": "请假",
    "多久": "期限",
    "几天": "期限",
    "时限": "期限",
}


def tokenize(text: str) -> set[str]:
    """分词并扩展通用业务同义词，避免按具体问题匹配。"""
    raw_words = set(jieba.lcut(text))
    words = {
        word.lower()
        for word in raw_words
        if len(word.strip()) > 1
        and word not in STOP_WORDS
        and re.search(r"[\w\u4e00-\u9fff]", word)
    }
    return words | {SYNONYMS[word] for word in raw_words if word in SYNONYMS}


class Corpus:
    """加载并验证不可变的本次资料快照。"""

    def __init__(self, path: Path) -> None:
        raw = path.read_bytes()
        self.digest = hashlib.sha256(raw).hexdigest()
        self.name = path.stem
        documents = [Document.model_validate(item) for item in json.loads(raw)]
        self.documents = {doc.document_id: doc for doc in documents}
        if len(self.documents) != len(documents):
            raise ValueError("文档 ID 重复")

    def search(self, query: str, top_k: int) -> list[dict]:
        """按标题与正文词匹配排序，返回摘要而非答案。"""
        terms = tokenize(query)
        results = []
        for doc in self.documents.values():
            title_terms = tokenize(doc.title)
            body_terms = tokenize(" ".join(chunk.text for chunk in doc.chunks))
            matched = terms & (title_terms | body_terms)
            score = 3 * len(terms & title_terms) + len(terms & body_terms)
            if score:
                results.append(
                    {
                        "document_id": doc.document_id,
                        "title": doc.title,
                        "version_date": doc.version_date,
                        "summary": doc.chunks[0].text[:160],
                        "score": score,
                        "matched_terms": sorted(matched),
                    }
                )
        return sorted(results, key=lambda row: (-row["score"], row["document_id"]))[
            :top_k
        ]
