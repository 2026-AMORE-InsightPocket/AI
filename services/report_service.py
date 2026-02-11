# AiService/services/report_service.py
"""
Report Service - Business logic for report generation
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Dict, Any

from langchain_core.messages import SystemMessage

from models.schemas import ChatRequest, GenerateReportResponse
from core.rag import RAGService
from core.vectorstore import VectorStore
from chains.custom_report import generate_custom_report_md, infer_title_from_md
import settings


logger = logging.getLogger("insightpocket.report_service")


class ReportService:
    """
    Service for handling report operations
    """

    def __init__(self, conn):
        """
        Initialize Report Service

        Args:
            conn: Oracle database connection
        """
        self.conn = conn
        self.rag_service = RAGService(conn)
        self.vectorstore = VectorStore(conn)

    def _keep_last_user_message(self, req: ChatRequest) -> ChatRequest:
        """Keep only the last user message"""
        users = [m for m in req.messages if m.role == "user"]
        if not users:
            return ChatRequest(messages=[])
        return ChatRequest(messages=[users[-1]])

    def _to_langchain_messages(self, req: ChatRequest) -> list:
        """
        Convert ChatRequest to LangChain messages

        Args:
            req: Chat request

        Returns:
            List of LangChain messages
        """
        from langchain_core.messages import HumanMessage, AIMessage

        messages = []

        for m in req.messages:
            text = m.content or ""

            # Attach card data
            if m.attachedData:
                card_blocks = []
                for c in m.attachedData:
                    lines = "\n".join([f"- {ln}" for ln in c.lines]) if c.lines else "- (no lines)"
                    card_blocks.append(f"[CARD] {c.title}\n{lines}")
                text += "\n\n" + "\n\n".join(card_blocks)

            if m.role == "user":
                messages.append(HumanMessage(content=text))
            else:
                messages.append(AIMessage(content=text))

        return messages

    def generate_custom_report(
        self,
        req: ChatRequest,
        use_rag: bool = True,
    ) -> GenerateReportResponse:
        """
        Generate custom report

        Args:
            req: Chat request with user's report request
            use_rag: Whether to use RAG for similar reports

        Returns:
            Generated report response
        """
        # Keep only the last user message
        req = self._keep_last_user_message(req)

        # Convert to LangChain messages
        lc_messages = self._to_langchain_messages(req)

        # Remove system message if present
        if lc_messages and isinstance(lc_messages[0], SystemMessage):
            lc_messages = lc_messages[1:]

        # Get RULE document
        rule_md = self.rag_service.get_rule_document()
        if not rule_md:
            logger.warning("[REPORT_SERVICE] RULE document not found, using empty")
            rule_md = ""

        logger.info(
            f"[REPORT_SERVICE][RULE_DOC] "
            f"length={len(rule_md)} chars"
        )

        # Generate report with RAG
        body_md = generate_custom_report_md(
            lc_messages=lc_messages,
            rule_md=rule_md,
            rag_service=self.rag_service if use_rag else None,
            use_rag=use_rag,
        )

        # Infer title from markdown
        title = infer_title_from_md(body_md, fallback="Custom Report")

        # Generate report ID
        report_id = VectorStore.new_report_id("report_custom")

        # Save to database
        self.vectorstore.upsert_document(
            doc_id=report_id,
            doc_type_id=settings.DOC_TYPE_CUSTOM,
            title=title,
            body_md=body_md,
            report_date=date.today(),
        )

        # Ingest to RAG (create embeddings)
        self.vectorstore.ingest_document(
            doc_id=report_id,
            body_md=body_md,
        )

        logger.info(
            f"[REPORT_SERVICE] Custom report generated: "
            f"id={report_id}, title={title}"
        )

        return GenerateReportResponse(
            report_id=report_id,
            body_md=body_md,
            title=title,
        )
