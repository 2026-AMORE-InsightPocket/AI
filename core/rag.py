# AiService/core/rag.py
"""
RAG (Retrieval-Augmented Generation) Service

Provides intelligent retrieval of relevant documents and context building
for chat and report generation.
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import logging

from .vectorstore import VectorStore
import settings


logger = logging.getLogger("insightpocket.rag")


class RAGService:
    """
    RAG Service for intelligent document retrieval
    """

    def __init__(self, conn):
        """
        Initialize RAG Service

        Args:
            conn: Oracle database connection
        """
        self.conn = conn
        self.vectorstore = VectorStore(conn)

    def search_relevant_documents(
        self,
        query: str,
        *,
        doc_types: Optional[List[str]] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        top_k: int = 5,
        min_similarity: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents using semantic search

        Args:
            query: Search query text
            doc_types: Filter by document types (["DAILY", "CUSTOM", "RULE"])
            date_from: Filter by date range (start)
            date_to: Filter by date range (end)
            top_k: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of relevant document chunks with metadata
        """
        # Map doc types to IDs
        doc_type_ids = None
        if doc_types:
            type_map = {
                "RULE": settings.DOC_TYPE_RULE,
                "DAILY": settings.DOC_TYPE_DAILY,
                "CUSTOM": settings.DOC_TYPE_CUSTOM,
            }
            doc_type_ids = [type_map[dt] for dt in doc_types if dt in type_map]

        # Perform similarity search
        results = self.vectorstore.similarity_search(
            query=query,
            top_k=top_k,
            doc_type_ids=doc_type_ids,
            date_from=date_from,
            date_to=date_to,
        )

        # Filter by similarity threshold
        filtered_results = [
            r for r in results
            if r.get("similarity", 0) >= min_similarity
        ]

        logger.info(
            f"[RAG] Query: '{query[:50]}...' | "
            f"Found: {len(results)} | "
            f"After filter (>={min_similarity}): {len(filtered_results)}"
        )

        return filtered_results

    def search_recent_daily_reports(
        self,
        query: str,
        days: int = 14,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search recent daily reports

        Args:
            query: Search query
            days: Number of recent days to search
            top_k: Maximum number of results

        Returns:
            List of relevant daily report chunks
        """
        date_to = datetime.now().date()
        date_from = date_to - timedelta(days=days)

        return self.search_relevant_documents(
            query=query,
            doc_types=["DAILY"],
            date_from=date_from,
            date_to=date_to,
            top_k=top_k,
        )

    def search_similar_custom_reports(
        self,
        query: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar custom reports

        Args:
            query: Search query
            top_k: Maximum number of results

        Returns:
            List of similar custom reports
        """
        return self.search_relevant_documents(
            query=query,
            doc_types=["CUSTOM"],
            top_k=top_k,
        )

    def build_context_for_chat(
        self,
        user_query: str,
        attached_cards: Optional[List[Dict[str, Any]]] = None,
        use_recent_reports: bool = True,
        max_context_chunks: int = 3,
    ) -> str:
        """
        Build context for chat completion

        Combines:
        1. Attached card data (if provided)
        2. Relevant recent daily reports (if enabled)

        Args:
            user_query: User's question
            attached_cards: List of attached card data
            use_recent_reports: Whether to include recent daily reports
            max_context_chunks: Maximum number of RAG chunks to include

        Returns:
            Formatted context string for LLM
        """
        context_parts = []

        # 1. Attached card data (highest priority)
        if attached_cards:
            card_lines = []
            for card in attached_cards:
                title = card.get("title", "")
                lines = card.get("lines", [])
                formatted_lines = "\n".join([f"  - {ln}" for ln in lines])
                card_lines.append(f"[CARD] {title}\n{formatted_lines}")

            if card_lines:
                context_parts.append(
                    "[USER_ATTACHED_DATA]\n" + "\n\n".join(card_lines)
                )

        # 2. Relevant past reports (for context)
        if use_recent_reports:
            recent_docs = self.search_recent_daily_reports(
                query=user_query,
                days=14,
                top_k=max_context_chunks,
            )

            if recent_docs:
                doc_lines = []
                for doc in recent_docs:
                    content = doc.get("content", "")[:500]  # Limit length
                    title = doc.get("title", "")
                    report_date = doc.get("report_date", "")
                    doc_lines.append(
                        f"[PAST_REPORT] {title} ({report_date})\n{content}..."
                    )

                if doc_lines:
                    context_parts.append(
                        "[RELEVANT_PAST_INSIGHTS]\n" + "\n\n".join(doc_lines)
                    )

        if not context_parts:
            return ""

        return "\n\n---\n\n".join(context_parts)

    def build_context_for_custom_report(
        self,
        user_request: str,
        attached_cards: Optional[List[Dict[str, Any]]] = None,
        use_similar_reports: bool = True,
        max_similar_reports: int = 2,
    ) -> str:
        """
        Build context for custom report generation

        Combines:
        1. Attached card data
        2. Similar past custom reports (for consistency)

        Args:
            user_request: User's report request
            attached_cards: List of attached card data
            use_similar_reports: Whether to include similar past reports
            max_similar_reports: Maximum number of similar reports to include

        Returns:
            Formatted context string for LLM
        """
        context_parts = []

        # 1. Attached card data
        if attached_cards:
            card_lines = []
            for card in attached_cards:
                title = card.get("title", "")
                lines = card.get("lines", [])
                formatted_lines = "\n".join([f"  - {ln}" for ln in lines])
                card_lines.append(f"[DATA] {title}\n{formatted_lines}")

            if card_lines:
                context_parts.append(
                    "[CURRENT_DATA]\n" + "\n\n".join(card_lines)
                )

        # 2. Similar past reports (for reference)
        if use_similar_reports:
            similar_reports = self.search_similar_custom_reports(
                query=user_request,
                top_k=max_similar_reports,
            )

            if similar_reports:
                report_lines = []
                for report in similar_reports:
                    content = report.get("content", "")[:600]
                    title = report.get("title", "")
                    report_lines.append(
                        f"[REFERENCE_REPORT] {title}\n{content}..."
                    )

                if report_lines:
                    context_parts.append(
                        "[SIMILAR_PAST_REPORTS_FOR_REFERENCE]\n" +
                        "\n\n".join(report_lines)
                    )

        if not context_parts:
            return ""

        return "\n\n---\n\n".join(context_parts)

    def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyze user query to determine intent

        Args:
            query: User query

        Returns:
            Dict with intent analysis:
            - needs_recent_data: bool
            - needs_historical_data: bool
            - time_range: Optional[str] (e.g., "last_week", "last_month")
            - mentioned_products: List[str]
        """
        query_lower = query.lower()

        # Time-related keywords
        time_keywords = {
            "오늘": "today",
            "어제": "yesterday",
            "이번 주": "this_week",
            "지난 주": "last_week",
            "이번 달": "this_month",
            "지난 달": "last_month",
            "최근": "recent",
        }

        time_range = None
        for kr, en in time_keywords.items():
            if kr in query_lower:
                time_range = en
                break

        # Historical analysis keywords
        historical_keywords = ["트렌드", "변화", "추세", "히스토리", "과거"]
        needs_historical = any(kw in query_lower for kw in historical_keywords)

        # Recent data keywords
        recent_keywords = ["현재", "지금", "최신"]
        needs_recent = any(kw in query_lower for kw in recent_keywords)

        return {
            "needs_recent_data": needs_recent or time_range in ["today", "this_week"],
            "needs_historical_data": needs_historical or time_range is not None,
            "time_range": time_range,
            "query_type": "analytical" if needs_historical else "informational",
        }

    def get_rule_document(self) -> Optional[str]:
        """
        Get the current RULE document

        Returns:
            RULE document body or None
        """
        rule_doc = self.vectorstore.get_latest_document_by_type(
            settings.DOC_TYPE_RULE
        )

        if not rule_doc:
            logger.warning("[RAG] RULE document not found")
            return None

        return rule_doc.get("body_md", "")
