"""
Core modules for InsightPocket AI Service

This package contains core functionality:
- embeddings: Embedding generation
- vectorstore: Vector storage and management
- rag: RAG (Retrieval-Augmented Generation) search
"""

from .embeddings import get_embeddings
from .vectorstore import VectorStore
from .rag import RAGService

__all__ = [
    "get_embeddings",
    "VectorStore",
    "RAGService",
]
