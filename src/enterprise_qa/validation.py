"""验证引用来源；不把字符串匹配等同于语义正确。"""

from enterprise_qa.schemas import Answer, Citation


def validate_citations(answer: Answer, read_documents: dict[str, dict]) -> None:
    """仅允许引用本次成功读取的版本与原文。"""
    for citation in answer.citations:
        document = read_documents.get(citation.document_id)
        if document is None or document["version_date"] != citation.version_date:
            raise ValueError("引用文档未读取或版本不匹配")
        chunks = {item["chunk_id"]: item["text"] for item in document["chunks"]}
        if (
            citation.chunk_id not in chunks
            or citation.quote not in chunks[citation.chunk_id]
        ):
            raise ValueError("引用片段不存在或引文不是原文子串")


def evidence_citations(read_documents: dict[str, dict]) -> list[Citation]:
    """中止时保留已取得的证据，不据此推断答案。"""
    return [
        Citation(
            document_id=doc["document_id"],
            version_date=doc["version_date"],
            chunk_id=chunk["chunk_id"],
            quote=chunk["text"],
        )
        for doc in read_documents.values()
        for chunk in doc["chunks"]
    ]
