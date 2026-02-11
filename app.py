# AiService/app.py
"""
InsightPocket AI Service - FastAPI Application

Refactored version with clean architecture:
- Routes only handle HTTP layer
- Business logic in service layer
- RAG integrated for intelligent context retrieval
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models.schemas import (
    ChatRequest,
    ChatResponse,
    GenerateReportResponse,
    RAGSearchRequest,
    RAGSearchResponse,
    RAGSearchResult,
)
from services.chat_service import ChatService
from services.report_service import ReportService
from core.rag import RAGService
from db import get_oracle_conn


# ===========================
# Logging Setup
# ===========================

logger = logging.getLogger("insightpocket")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


# ===========================
# FastAPI App
# ===========================

app = FastAPI(
    title="InsightPocket AI Service",
    description="AI-powered insights for LANEIGE Amazon data",
    version="2.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://43.202.180.67",
        "http://43.202.180.67:80",
        "https://boradora.store",
        "https://insight-pocket.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================
# Health Check
# ===========================

@app.get("/health")
def health():
    """Health check endpoint"""
    return {"ok": True, "version": "2.0.0"}


# ===========================
# Chat API
# ===========================

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Chat with AI assistant

    Supports:
    - Conversational AI with context
    - Attached card data from Pocket
    - RAG retrieval from past reports
    """
    conn = None
    try:
        conn = get_oracle_conn()
        chat_service = ChatService(conn)
        return chat_service.process_chat(req, use_rag=True)
    except Exception as e:
        logger.error(f"[CHAT] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ===========================
# Report API
# ===========================

@app.post("/api/report/custom", response_model=GenerateReportResponse)
def report_custom(req: ChatRequest):
    """
    Generate custom report

    Supports:
    - User request with attached data
    - RAG retrieval from similar past reports
    - Consistent analysis framework
    """
    conn = None
    try:
        conn = get_oracle_conn()
        report_service = ReportService(conn)
        return report_service.generate_custom_report(req, use_rag=True)
    except Exception as e:
        logger.error(f"[REPORT_CUSTOM] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ===========================
# RAG Search API (for debugging/testing)
# ===========================

@app.post("/api/rag/search", response_model=RAGSearchResponse)
def rag_search(req: RAGSearchRequest):
    """
    Search documents using RAG

    For debugging and testing RAG functionality.
    """
    conn = None
    try:
        conn = get_oracle_conn()
        rag_service = RAGService(conn)

        results = rag_service.search_relevant_documents(
            query=req.query,
            doc_types=req.doc_types,
            date_from=req.date_from,
            date_to=req.date_to,
            top_k=req.top_k,
        )

        # Convert to response schema
        result_list = [
            RAGSearchResult(
                content=r["content"],
                doc_id=r["doc_id"],
                title=r["title"],
                doc_type_id=r["doc_type_id"],
                report_date=r.get("report_date"),
                similarity=r["similarity"],
            )
            for r in results
        ]

        return RAGSearchResponse(
            results=result_list,
            query=req.query,
            total_found=len(result_list),
        )
    except Exception as e:
        logger.error(f"[RAG_SEARCH] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ===========================
# Main Entry
# ===========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
