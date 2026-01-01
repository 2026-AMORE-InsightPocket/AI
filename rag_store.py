# AiService/rag_store.py
from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple
from datetime import date
import uuid
import re

import oracledb
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
    md = (md or "").strip()
    if not md:
        return []

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

        if len(buf) + len(p) + 2 > max_chars:
            flush_buf()
            while len(p) > max_chars:
                part = p[:max_chars]
                chunks.append(part.strip())
                p = p[max_chars - overlap :]
            buf = p
        else:
            buf = (buf + "\n\n" + p).strip() if buf else p

    flush_buf()
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
    use_safe_insert: bool = True,   # ⭐ executemany가 계속 터지면 True 유지 추천
) -> int:
    """
    rag_doc_chunks에 chunk + embedding 저장

    주의:
    - vec(List[float]) executemany 바인딩이 ORA-01484를 유발할 수 있음
    - 가장 안전한 방식: embedding 포함 insert는 loop execute (use_safe_insert=True)
    """
    if not chunks:
        return 0

    emb = OpenAIEmbeddings(model=embedding_model, api_key=settings.OPENAI_API_KEY)
    vectors = emb.embed_documents(chunks)  # List[List[float]]

    cur = conn.cursor()

    # embedding 바인드를 VECTOR로 명시
    try:
        cur.setinputsizes(None, None, None, None, None, oracledb.DB_TYPE_VECTOR)
    except Exception:
        pass

    sql = """
    INSERT INTO rag_doc_chunks (
      chunk_id, doc_id, chunk_index, content, token_count, embedding, created_at
    ) VALUES (
      :1, :2, :3, :4, :5, :6, SYSTIMESTAMP
    )
    """

    rows: List[Tuple[Any, ...]] = []
    for idx, (text, vec) in enumerate(zip(chunks, vectors)):
        chunk_id = uuid.uuid4().hex
        token_count = None
        rows.append((chunk_id, doc_id, idx, text, token_count, vec))

    # ✅ 안전모드(추천): 개별 execute
    if use_safe_insert:
        for r in rows:
            cur.execute(sql, r)
        conn.commit()
        return len(rows)

    # 성능모드: executemany (여기서 ORA-01484 터질 수 있음)
    cur.executemany(sql, rows)
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
    chunks = _simple_md_chunk(body_md, max_chars=chunk_max_chars, overlap=chunk_overlap)
    delete_chunks_for_doc(conn, doc_id)
    n = insert_chunks_with_embeddings(
        conn,
        doc_id=doc_id,
        chunks=chunks,
        embedding_model=embedding_model,
        use_safe_insert=True,  # ⭐ 일단 안정적으로 가자
    )
    return {"doc_id": doc_id, "chunk_count": n}