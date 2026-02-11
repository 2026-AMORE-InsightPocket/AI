# AiService/models/schemas.py
"""
Pydantic models for API request/response schemas
"""
from __future__ import annotations

from typing import List, Optional, Literal
from datetime import date
from pydantic import BaseModel, Field


# ===========================
# Chat Schemas
# ===========================

Role = Literal["user", "assistant"]


class AttachedCard(BaseModel):
    """
    Card data attached to a message (from Pocket)
    """
    title: str = Field(..., description="Card title")
    lines: List[str] = Field(default_factory=list, description="Card content lines")


class ChatMessage(BaseModel):
    """
    Single message in a chat conversation
    """
    role: Role = Field(..., description="Message role (user or assistant)")
    content: str = Field(..., description="Message content")
    attachedData: Optional[List[AttachedCard]] = Field(
        None,
        description="Attached card data (from Pocket)"
    )


class ChatRequest(BaseModel):
    """
    Request for chat completion
    """
    messages: List[ChatMessage] = Field(..., description="Conversation history")
    selectedDataIds: Optional[List[str]] = Field(
        None,
        description="Selected data IDs (for future DB lookup)"
    )


class ChatResponse(BaseModel):
    """
    Response from chat completion
    """
    answer: str = Field(..., description="AI assistant's response")


# ===========================
# Report Schemas
# ===========================

class GenerateReportResponse(BaseModel):
    """
    Response from report generation
    """
    report_id: str = Field(..., description="Generated report ID")
    body_md: str = Field(..., description="Report body in Markdown")
    title: Optional[str] = Field(None, description="Report title")


# ===========================
# RAG Schemas
# ===========================

class RAGSearchRequest(BaseModel):
    """
    Request for RAG search
    """
    query: str = Field(..., description="Search query")
    doc_types: Optional[List[str]] = Field(
        None,
        description="Document types to search (DAILY, CUSTOM, RULE)"
    )
    date_from: Optional[date] = Field(None, description="Start date filter")
    date_to: Optional[date] = Field(None, description="End date filter")
    top_k: int = Field(5, description="Number of results to return")


class RAGSearchResult(BaseModel):
    """
    Single result from RAG search
    """
    content: str = Field(..., description="Chunk content")
    doc_id: str = Field(..., description="Document ID")
    title: str = Field(..., description="Document title")
    doc_type_id: int = Field(..., description="Document type ID")
    report_date: Optional[date] = Field(None, description="Report date")
    similarity: float = Field(..., description="Similarity score (0-1)")


class RAGSearchResponse(BaseModel):
    """
    Response from RAG search
    """
    results: List[RAGSearchResult] = Field(..., description="Search results")
    query: str = Field(..., description="Original query")
    total_found: int = Field(..., description="Total number of results found")
