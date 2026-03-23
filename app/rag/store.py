"""
ChromaDB vector store for the Plantifique operational policy doc.

- Uses ChromaDB's default embedding function (all-MiniLM-L6-v2, local, free).
- Collection is built lazily on first query and persisted to disk.
- Fully controlled by the WANT_TO_USE_RAG env var (checked by caller).
- All RAG calls are timed and logged at INFO level.
"""
import logging
import os
import time
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

from app.rag.chunker import load_chunks

logger = logging.getLogger(__name__)

COLLECTION_NAME = "plantifique_ops_v1"
CHROMA_PERSIST_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")

_client: Optional[chromadb.PersistentClient] = None
_collection = None


def _get_collection():
    global _client, _collection

    if _collection is not None:
        return _collection

    logger.info("[RAG] Initializing ChromaDB at %s", CHROMA_PERSIST_PATH)
    _client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)

    ef = embedding_functions.DefaultEmbeddingFunction()

    _collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    if _collection.count() == 0:
        t0 = time.perf_counter()
        logger.info("[RAG] Collection empty — building index from policy doc...")
        chunks = load_chunks()
        _collection.add(
            documents=[c["text"] for c in chunks],
            ids=[c["id"] for c in chunks],
            metadatas=[{"section": c["section"]} for c in chunks],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info("[RAG] Indexed %d chunks in %.1fms", len(chunks), elapsed_ms)
    else:
        logger.info("[RAG] Loaded existing collection (%d chunks)", _collection.count())

    return _collection


def query_rag(query: str, n_results: int = 3) -> str:
    """
    Retrieves the most relevant policy chunks for a given query string.
    Returns a single formatted string ready to inject into a prompt,
    or an empty string if no results found.

    Args:
        query:     The search query (e.g. product title + tier + evaluation context).
        n_results: Max number of chunks to retrieve (default 3).

    Returns:
        Concatenated relevant policy text, or "" on failure/no results.
    """
    t0 = time.perf_counter()
    try:
        collection = _get_collection()
        actual_n = min(n_results, collection.count())
        if actual_n == 0:
            logger.warning("[RAG] Collection is empty — skipping retrieval")
            return ""

        results = collection.query(
            query_texts=[query],
            n_results=actual_n,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        docs = results.get("documents", [[]])[0]
        sections = [m.get("section", "?") for m in results.get("metadatas", [[]])[0]]

        logger.info(
            "[RAG] Query='%.60s...' → %d results in %.1fms | sections=%s",
            query, len(docs), elapsed_ms, sections,
        )

        if not docs:
            return ""

        return "\n\n".join(docs)

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.error("[RAG] Query failed after %.1fms: %s", elapsed_ms, exc)
        return ""
