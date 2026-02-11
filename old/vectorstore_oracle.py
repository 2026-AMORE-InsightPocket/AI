import uuid
from typing import List, Dict, Any

from langchain_community.vectorstores import OracleVS  # Oracle Vector Store
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from db import get_oracle_conn

# Embeddings (예: OpenAI)
from langchain_openai import OpenAIEmbeddings


TABLE_NAME = "RAG_CHUNKS"   # Oracle에 생성될 벡터 테이블 이름


def get_embeddings():
    # OpenAI 사용 예시 (원하면 OCI/로컬로 교체 가능)
    return OpenAIEmbeddings(model="text-embedding-3-small")


def get_vectorstore():
    conn = get_oracle_conn()
    embeddings = get_embeddings()

    # OracleVS는 내부적으로 Oracle Vector Search(VECTOR 타입/인덱스)를 사용
    vs = OracleVS(
        client=conn,               # oracledb connection
        embedding_function=embeddings,
        table_name=TABLE_NAME,
    )
    return vs, conn


def ingest_daily_rank_report(
    report_date: str,  # "2025-12-27"
    text: str,
    metadata: Dict[str, Any],
):
    """
    랭킹 히스토리 기반으로 생성된 '일일 요약 리포트'를 Vector DB에 저장.
    - report_date 기준으로 조회/비교하기 쉽게 metadata에 박아둠
    """
    vs, conn = get_vectorstore()
    try:
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
        chunks = splitter.split_text(text)

        docs: List[Document] = []
        for i, chunk in enumerate(chunks):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "doc_type": "DAILY_RANK_REPORT",
                        "report_date": report_date,
                        "chunk_idx": i,
                        **metadata,
                    },
                )
            )

        # 문서 ID를 고정하고 싶으면 직접 ids를 넣어도 됨
        ids = [str(uuid.uuid4()) for _ in docs]
        vs.add_documents(docs, ids=ids)
        conn.commit()
        return {"inserted": len(docs)}

    finally:
        conn.close()


def search_reports(query: str, k: int = 6, report_date: str | None = None):
    vs, conn = get_vectorstore()
    try:
        # OracleVS가 metadata 필터를 지원하면 아래처럼 (지원 형태는 버전에 따라 다를 수 있음)
        # 지원 안 하면: 검색 결과에서 report_date로 후필터링하면 됨.
        results = vs.similarity_search(query, k=k)
        if report_date:
            results = [d for d in results if d.metadata.get("report_date") == report_date]
        return results
    finally:
        conn.close()