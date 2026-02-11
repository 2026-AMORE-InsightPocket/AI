# AiService/services/chat_service.py
"""
Chat Service - Business logic for chat operations
"""
from __future__ import annotations

import logging
import json
from typing import Dict, Any

from models.schemas import ChatRequest, ChatResponse
from core.rag import RAGService
from chains.chat import generate_chat_response


logger = logging.getLogger("insightpocket.chat_service")


class ChatService:
    """
    Service for handling chat operations
    """

    def __init__(self, conn):
        """
        Initialize Chat Service

        Args:
            conn: Oracle database connection
        """
        self.conn = conn
        self.rag_service = RAGService(conn)

    def _safe_preview(self, text: str, limit: int = 500) -> str:
        """Safe preview of text for logging"""
        if not text:
            return ""
        text = str(text)
        return text if len(text) <= limit else text[:limit] + "...(truncated)"

    def process_chat(
        self,
        req: ChatRequest,
        use_rag: bool = True,
    ) -> ChatResponse:
        """
        Process chat request and generate response

        Args:
            req: Chat request
            use_rag: Whether to use RAG retrieval

        Returns:
            Chat response
        """
        # Log request
        logger.info(
            "[CHAT_SERVICE][REQ] %s",
            json.dumps(
                [
                    {
                        "role": m.role,
                        "content": self._safe_preview(m.content),
                        "attachedData": (
                            [
                                {
                                    "title": c.title,
                                    "lines_preview": [
                                        self._safe_preview(x, 120)
                                        for x in (c.lines or [])[:30]
                                    ]
                                }
                                for c in (m.attachedData or [])
                            ]
                            if m.attachedData else None
                        ),
                    }
                    for m in req.messages
                ],
                ensure_ascii=False,
            ),
        )

        if req.selectedDataIds:
            logger.info("[CHAT_SERVICE][SELECTED_IDS] %s", req.selectedDataIds)

        # Generate response
        answer = generate_chat_response(req, self.rag_service, use_rag=use_rag)

        # Log response
        logger.info("[CHAT_SERVICE][RESP] %s", self._safe_preview(answer, 800))

        return ChatResponse(answer=answer)
