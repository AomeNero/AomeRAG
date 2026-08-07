"""稳定内容哈希 + 确定性 chunk id。"""

from __future__ import annotations

import hashlib


def content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def chunk_id(source_doc: str, chunk_index: int) -> str:
    """确定性、Zvec 安全的 chunk id。

    Zvec 文档 id 不接受空格/中文/路径分隔符，所以不能直接用 source_doc。
    用 source_doc + 索引的短哈希——跨重新入库稳定（upsert 才能替换），
    且只含 [0-9a-f#] 字符（全部 Zvec 安全）。source_doc 本身存成字段用于过滤/展示。"""
    h = hashlib.sha1(source_doc.encode("utf-8")).hexdigest()[:16]
    return f"{h}#{chunk_index}"

