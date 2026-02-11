# AiService/core/vectorstore.py
"""
Vector Store module - Unified interface for document storage and retrieval

Combines functionality from rag_store.py and vectorstore_oracle.py
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple
from datetime import date
import uuid
import re

import oracledb
from .embeddings import get_embeddings
import settings


def _lob_to_str(x: Any) -> str:
    """Convert Oracle LOB to string"""
    if x is None:
        return ""
    if hasattr(x, "read") and callable(getattr(x, "read")):
        try:
            return x.read()
        except Exception:
            return str(x)
    return str(x)


class VectorStore:
    """
    Unified Vector Store for managing documents and embeddings
    """

    def __init__(self, conn):
        """
        Initialize VectorStore

        Args:
            conn: Oracle database connection
        """
        self.conn = conn
        self.embeddings = get_embeddings()

    # -------------------------
    # Document Management (rag_docs)
    # -------------------------

    def upsert_document(
        self,
        *,
        doc_id: str,
        doc_type_id: int,
        title: str,
        body_md: str,
        report_date: Optional[date] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Insert or update a document in rag_docs table

        Args:
            doc_id: Unique document identifier
            doc_type_id: Document type (0=RULE, 1=DAILY, 2=CUSTOM)
            title: Document title
            body_md: Document body in Markdown
            report_date: Optional report date
            metadata: Optional metadata dict (for future extension)

        Returns:
            Dict with doc_id and title
        """
        cur = self.conn.cursor()

        # Try UPDATE first
        cur.execute(
            """
            UPDATE rag_docs
               SET doc_type_id = :doc_type_id,
                   title       = :title,
                   body_md     = :body_md,
                   report_date = :report_date,
                   created_at  = CURRENT_TIMESTAMP
             WHERE doc_id = :doc_id
            """,
            {
                "doc_id": doc_id,
                "doc_type_id": doc_type_id,
                "title": title,
                "body_md": body_md,
                "report_date": report_date,
            },
        )

        # If not found, INSERT
        if cur.rowcount == 0:
            cur.execute(
                """
                INSERT INTO rag_docs (doc_id, doc_type_id, title, body_md, report_date, created_at)
                VALUES (:doc_id, :doc_type_id, :title, :body_md, :report_date, CURRENT_TIMESTAMP)
                """,
                {
                    "doc_id": doc_id,
                    "doc_type_id": doc_type_id,
                    "title": title,
                    "body_md": body_md,
                    "report_date": report_date,
                },
            )

        self.conn.commit()
        return {"doc_id": doc_id, "title": title}

    def get_document_by_id(self, doc_id: str) -> Optional[str]:
        """
        Get document body by doc_id

        Args:
            doc_id: Document identifier

        Returns:
            Document body as string or None if not found
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT body_md FROM rag_docs WHERE doc_id = :doc_id",
            {"doc_id": doc_id},
        )
        row = cur.fetchone()
        return _lob_to_str(row[0]) if row and row[0] else None

    def get_latest_document_by_type(self, doc_type_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the latest document of a specific type

        Args:
            doc_type_id: Document type

        Returns:
            Dict with doc_id, title, body_md or None
        """
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT doc_id, title, body_md
              FROM rag_docs
             WHERE doc_type_id = :doc_type_id
             ORDER BY created_at DESC
             FETCH FIRST 1 ROWS ONLY
            """,
            {"doc_type_id": doc_type_id},
        )
        row = cur.fetchone()
        if not row:
            return None

        return {
            "doc_id": row[0],
            "title": row[1],
            "body_md": _lob_to_str(row[2]),
        }

    # -------------------------
    # Chunk Management (rag_doc_chunks)
    # -------------------------

    def _chunk_markdown(
        self,
        md: str,
        max_chars: int = 1200,
        overlap: int = 120
    ) -> List[str]:
        """
        Split markdown text into chunks

        Args:
            md: Markdown text
            max_chars: Maximum characters per chunk
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
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
                    p = p[max_chars - overlap:]
                buf = p
            else:
                buf = (buf + "\n\n" + p).strip() if buf else p

        flush_buf()
        return chunks

    def delete_chunks(self, doc_id: str) -> None:
        """
        Delete all chunks for a document

        Args:
            doc_id: Document identifier
        """
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM rag_doc_chunks WHERE doc_id = :doc_id",
            {"doc_id": doc_id}
        )
        self.conn.commit()

    def insert_chunks_with_embeddings(
        self,
        *,
        doc_id: str,
        chunks: List[str],
        use_safe_insert: bool = True,
    ) -> int:
        """
        Insert chunks with their embeddings

        Args:
            doc_id: Document identifier
            chunks: List of text chunks
            use_safe_insert: Use safe insert mode (loop execute instead of executemany)

        Returns:
            Number of chunks inserted
        """
        if not chunks:
            return 0

        # Generate embeddings for all chunks
        vectors = self.embeddings.embed_documents(chunks)

        cur = self.conn.cursor()

        # Set input size for VECTOR type
        try:
            cur.setinputsizes(None, None, None, None, None, oracledb.DB_TYPE_VECTOR)
        except Exception:
            pass

        sql = """
        INSERT INTO rag_doc_chunks (
          chunk_id, doc_id, chunk_index, content, token_count, embedding, created_at
        ) VALUES (
          :1, :2, :3, :4, :5, :6, CURRENT_TIMESTAMP
        )
        """

        rows: List[Tuple[Any, ...]] = []
        for idx, (text, vec) in enumerate(zip(chunks, vectors)):
            chunk_id = uuid.uuid4().hex
            token_count = None
            rows.append((chunk_id, doc_id, idx, text, token_count, vec))

        # Safe mode: individual execute (recommended to avoid ORA-01484)
        if use_safe_insert:
            for r in rows:
                cur.execute(sql, r)
            self.conn.commit()
            return len(rows)

        # Performance mode: executemany (may throw ORA-01484)
        cur.executemany(sql, rows)
        self.conn.commit()
        return len(rows)

    def ingest_document(
        self,
        *,
        doc_id: str,
        body_md: str,
        chunk_max_chars: int = 1200,
        chunk_overlap: int = 120,
    ) -> Dict[str, Any]:
        """
        Chunk a document and store with embeddings

        Args:
            doc_id: Document identifier
            body_md: Document body in Markdown
            chunk_max_chars: Maximum characters per chunk
            chunk_overlap: Overlap between chunks

        Returns:
            Dict with doc_id and chunk_count
        """
        chunks = self._chunk_markdown(
            body_md,
            max_chars=chunk_max_chars,
            overlap=chunk_overlap
        )

        self.delete_chunks(doc_id)

        n = self.insert_chunks_with_embeddings(
            doc_id=doc_id,
            chunks=chunks,
            use_safe_insert=True,
        )

        return {"doc_id": doc_id, "chunk_count": n}

    # -------------------------
    # Search (for RAG)
    # -------------------------

    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        doc_type_ids: Optional[List[int]] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search using embeddings

        Args:
            query: Search query
            top_k: Number of results to return
            doc_type_ids: Filter by document types
            date_from: Filter by date range (start)
            date_to: Filter by date range (end)

        Returns:
            List of dicts with chunk content, doc_id, title, similarity score
        """
        # Generate query embedding
        query_vec = self.embeddings.embed_query(query)

        # Build WHERE clause for filters
        where_clauses = []
        params = {"query_vec": query_vec, "top_k": top_k}

        if doc_type_ids:
            placeholders = ", ".join([f":dtype_{i}" for i in range(len(doc_type_ids))])
            where_clauses.append(f"d.doc_type_id IN ({placeholders})")
            for i, dtype in enumerate(doc_type_ids):
                params[f"dtype_{i}"] = dtype

        if date_from:
            where_clauses.append("d.report_date >= :date_from")
            params["date_from"] = date_from

        if date_to:
            where_clauses.append("d.report_date <= :date_to")
            params["date_to"] = date_to

        where_sql = " AND " + " AND ".join(where_clauses) if where_clauses else ""

        # Oracle Vector Search query
        sql = f"""
        SELECT
            c.content,
            c.doc_id,
            d.title,
            d.doc_type_id,
            d.report_date,
            VECTOR_DISTANCE(c.embedding, :query_vec, COSINE) as distance
        FROM rag_doc_chunks c
        JOIN rag_docs d ON c.doc_id = d.doc_id
        WHERE 1=1 {where_sql}
        ORDER BY distance ASC
        FETCH FIRST :top_k ROWS ONLY
        """

        cur = self.conn.cursor()
        cur.execute(sql, params)

        results = []
        for row in cur.fetchall():
            results.append({
                "content": _lob_to_str(row[0]),
                "doc_id": row[1],
                "title": row[2],
                "doc_type_id": row[3],
                "report_date": row[4],
                "distance": float(row[5]),
                "similarity": 1 - float(row[5]),  # Convert distance to similarity
            })

        return results

    # -------------------------
    # Utility
    # -------------------------

    @staticmethod
    def new_report_id(prefix: str = "report") -> str:
        """
        Generate a new unique report ID

        Args:
            prefix: Prefix for the ID

        Returns:
            Unique report ID
        """
        return f"{prefix}_{uuid.uuid4().hex}"
