# AiService/rag_store.py
from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple
from datetime import date
import uuid
import re

from langchain_openai import OpenAIEmbeddings

import settings


def _lob_to_str(x: Any) -> str:
    if x is None:
        return ""
    if hasattr(x, "read") and callable(getattr(x, "read")):
        try:
            return x.read()
        except Exception:
            return str(x)
    return str(x)


def load_rule_doc_body(conn, doc_id: str) -> str:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT body_md
        FROM rag_docs
        WHERE doc_id = :doc_id
        """,
        {"doc_id": doc_id},
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"RULE_DOC not found: {doc_id}")
    return _lob_to_str(row[0])


# -------------------------
# 1) rag_docs 저장 (UPSERT)
# -------------------------
def upsert_report_doc(
    conn,
    *,
    doc_id: str,
    doc_type_id: int,
    title: str,
    body_md: str,
    report_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    rag_docs에 레포트 저장 (doc_id 기준 MERGE).
    - daily는 doc_id를 날짜로 고정하는 게 보통: daily_YYYY-MM-DD
    """
    cur = conn.cursor()
    cur.execute(
        """
        MERGE INTO rag_docs t
        USING (SELECT :doc_id AS doc_id FROM dual) s
        ON (t.doc_id = s.doc_id)
        WHEN MATCHED THEN UPDATE SET
          t.doc_type_id = :doc_type_id,
          t.title = :title,
          t.body_md = :body_md,
          t.report_date = :report_date,
          t.created_at = SYSTIMESTAMP
        WHEN NOT MATCHED THEN INSERT (
          doc_id, doc_type_id, title, body_md, report_date, created_at
        ) VALUES (
          :doc_id, :doc_type_id, :title, :body_md, :report_date, SYSTIMESTAMP
        )
        """,
        {
            "doc_id": doc_id,
            "doc_type_id": doc_type_id,
            "title": title,
            "body_md": body_md,
            "report_date": report_date,
        },
    )
    conn.commit()
    return {"doc_id": doc_id, "title": title}


# -------------------------
# 2) chunking
# -------------------------
def _simple_md_chunk(md: str, max_chars: int = 1200, overlap: int = 120) -> List[str]:
    """
    아주 단순한 chunker (MVP)
    - Markdown을 문단 단위로 쪼개되, 너무 길면 max_chars 기준으로 split
    - overlap은 RAG 품질을 위한 약간의 겹침
    """
    md = (md or "").strip()
    if not md:
        return []

    # 큰 구분 먼저: 빈 줄 2개 이상 기준
    paras = re.split(r"\n{2,}", md)
    chunks: List[str] = []
    buf = ""

    def flush_buf():
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
        buf = ""

    for p in paras:
        p = p.strip()
        if not p:
            continue

        # buf에 붙였을 때 너무 커지면 flush
        if len(buf) + len(p) + 2 > max_chars:
            flush_buf()
            # p 자체가 너무 길면 강제로 잘라서 넣기
            while len(p) > max_chars:
                part = p[:max_chars]
                chunks.append(part.strip())
                p = p[max_chars - overlap :]  # overlap 유지
            buf = p
        else:
            buf = (buf + "\n\n" + p).strip() if buf else p

    flush_buf()

    # overlap 처리(문단 기반이라 이미 약간 자연스럽지만, 여기선 추가 처리 안 함)
    return chunks


# -------------------------
# 3) chunks delete + insert
# -------------------------
def delete_chunks_for_doc(conn, doc_id: str) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM rag_doc_chunks WHERE doc_id = :doc_id", {"doc_id": doc_id})
    conn.commit()


def insert_chunks_with_embeddings(
    conn,
    *,
    doc_id: str,
    chunks: List[str],
    embedding_model: str = "text-embedding-3-small",
) -> int:
    """
    rag_doc_chunks에 chunk + embedding 저장
    - embedding VECTOR(1536) 컬럼에 list[float]로 넣는 방식(드라이버/DB 지원 전제)
    """
    if not chunks:
        return 0

    emb = OpenAIEmbeddings(model=embedding_model, api_key=settings.OPENAI_API_KEY)
    vectors = emb.embed_documents(chunks)  # List[List[float]]

    cur = conn.cursor()

    rows: List[Tuple[Any, ...]] = []
    for idx, (text, vec) in enumerate(zip(chunks, vectors)):
        chunk_id = uuid.uuid4().hex  # VARCHAR2(64) 충분
        token_count = None  # 필요하면 추후 계산
        rows.append((chunk_id, doc_id, idx, text, token_count, vec))

    cur.executemany(
        """
        INSERT INTO rag_doc_chunks (
          chunk_id, doc_id, chunk_index, content, token_count, embedding, created_at
        ) VALUES (
          :1, :2, :3, :4, :5, :6, SYSTIMESTAMP
        )
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def ingest_doc_to_rag(
    conn,
    *,
    doc_id: str,
    body_md: str,
    chunk_max_chars: int = 1200,
    chunk_overlap: int = 120,
    embedding_model: str = "text-embedding-3-small",
) -> Dict[str, Any]:
    """
    doc 본문을 chunk로 나누고, 기존 chunks 삭제 후 새로 삽입
    """
    chunks = _simple_md_chunk(body_md, max_chars=chunk_max_chars, overlap=chunk_overlap)
    delete_chunks_for_doc(conn, doc_id)
    n = insert_chunks_with_embeddings(
        conn,
        doc_id=doc_id,
        chunks=chunks,
        embedding_model=embedding_model,
    )
    return {"doc_id": doc_id, "chunk_count": n}