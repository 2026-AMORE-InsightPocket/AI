# AiService/core/embeddings.py
"""
Embedding generation module

Provides unified interface for embedding generation using OpenAI.
"""
from __future__ import annotations

from typing import List
from langchain_openai import OpenAIEmbeddings
import settings


_embeddings_cache = None


def get_embeddings(model: str = "text-embedding-3-small") -> OpenAIEmbeddings:
    """
    Get or create OpenAI embeddings instance.

    Uses singleton pattern to avoid recreating the embeddings object.

    Args:
        model: OpenAI embedding model name

    Returns:
        OpenAIEmbeddings instance
    """
    global _embeddings_cache

    if _embeddings_cache is None:
        _embeddings_cache = OpenAIEmbeddings(
            model=model,
            api_key=settings.OPENAI_API_KEY
        )

    return _embeddings_cache


def embed_text(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """
    Generate embedding for a single text.

    Args:
        text: Text to embed
        model: OpenAI embedding model name

    Returns:
        Embedding vector as list of floats
    """
    emb = get_embeddings(model)
    return emb.embed_query(text)


def embed_documents(
    texts: List[str],
    model: str = "text-embedding-3-small"
) -> List[List[float]]:
    """
    Generate embeddings for multiple documents.

    Args:
        texts: List of texts to embed
        model: OpenAI embedding model name

    Returns:
        List of embedding vectors
    """
    emb = get_embeddings(model)
    return emb.embed_documents(texts)
