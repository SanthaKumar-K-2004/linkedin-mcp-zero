from __future__ import annotations

import math
import re
from typing import Any

import structlog

logger = structlog.get_logger()

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


class VectorStorage:
    """Vector database manager utilizing Qdrant with local/in-memory graceful fallback."""

    def __init__(self, collection_name: str = "resumes", vector_size: int = 384) -> None:
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.client = None
        self._fallback_db: dict[str, tuple[list[float], dict[str, Any]]] = {}
        if QDRANT_AVAILABLE:
            try:
                self.client = QdrantClient(":memory:")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )
                logger.info("Initialized in-memory Qdrant client collection", collection=self.collection_name)
            except Exception as e:
                logger.warning("Failed to initialize Qdrant client, using local dictionary fallback", error=str(e))
                self.client = None

    def upsert(self, doc_id: str, vector: list[float], payload: dict[str, Any]) -> None:
        """Insert or update a document vector and payload metadata."""
        if self.client:
            try:
                from qdrant_client.models import PointStruct

                # Simple integer conversion for qdrant ID limits
                numeric_id = int(re.sub(r"\D", "", doc_id)) if any(c.isdigit() for c in doc_id) else hash(doc_id)
                numeric_id = abs(numeric_id) % (10**8)

                self.client.upsert(
                    collection_name=self.collection_name,
                    points=[PointStruct(id=numeric_id, vector=vector, payload={"doc_id": doc_id, **payload})],
                )
                logger.info("Upserted document into Qdrant", doc_id=doc_id)
                return
            except Exception as e:
                logger.warning("Qdrant upsert failed, using fallback database", error=str(e))

        self._fallback_db[doc_id] = (vector, payload)
        logger.info("Upserted document into local dictionary fallback", doc_id=doc_id)

    def search(self, vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
        """Search similar document vectors using cosine similarity."""
        if self.client:
            try:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=vector,
                    limit=limit,
                )
                return [{"id": r.id, "score": r.score, **(r.payload or {})} for r in results]
            except Exception as e:
                logger.warning("Qdrant search failed, using fallback database", error=str(e))

        scored = []
        for doc_id, (v, payload) in self._fallback_db.items():
            dot = sum(a * b for a, b in zip(vector, v))
            norm_a = math.sqrt(sum(a**2 for a in vector))
            norm_b = math.sqrt(sum(b**2 for b in v))
            score = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
            scored.append({"doc_id": doc_id, "score": score, **payload})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]
