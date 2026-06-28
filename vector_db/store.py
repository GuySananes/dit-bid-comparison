from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from config import settings


@dataclass
class SearchResult:
    id: str
    text: str
    metadata: dict[str, Any]
    score: float  # cosine similarity, 0–1 (higher = more similar)


class VectorStore:
    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(
            path=settings.VECTOR_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        self._model = SentenceTransformer(settings.EMBEDDING_MODEL)

        self._mkts = self._client.get_or_create_collection(
            settings.VECTOR_DB_COLLECTION_MKT,
            metadata={"hnsw:space": "cosine"},
        )
        self._decisions = self._client.get_or_create_collection(
            settings.VECTOR_DB_COLLECTION_DECISIONS,
            metadata={"hnsw:space": "cosine"},
        )
        self._specs = self._client.get_or_create_collection(
            settings.VECTOR_DB_COLLECTION_SPECS,
            metadata={"hnsw:space": "cosine"},
        )

    # ── internal ──────────────────────────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()

    @staticmethod
    def _stable_id(prefix: str, text: str) -> str:
        digest = hashlib.sha1(text.encode()).hexdigest()[:12]
        return f"{prefix}_{digest}"

    @staticmethod
    def _distances_to_scores(distances: list[float]) -> list[float]:
        # ChromaDB cosine space returns distances (0 = identical, 2 = opposite).
        # Convert to similarity score in [0, 1].
        return [max(0.0, 1.0 - d / 2.0) for d in distances]

    # ── approved_mkts ─────────────────────────────────────────────────────────

    def add_mkt(
        self,
        canonical_name: str,
        aliases: list[str],
        metadata: dict[str, Any],
    ) -> None:
        """Add a known part number with all its aliases as a single searchable document."""
        alias_str = " ".join([canonical_name] + aliases)
        doc_id = self._stable_id("mkt", canonical_name.lower())

        meta = {
            "canonical_name": canonical_name,
            "added_at": str(date.today()),
            **metadata,
        }

        self._mkts.upsert(
            ids=[doc_id],
            embeddings=[self._embed(alias_str)],
            documents=[alias_str],
            metadatas=[meta],
        )

    def query_mkt(self, mkt_string: str, top_k: int = 5) -> list[SearchResult]:
        """Return the closest known part numbers to the given string."""
        results = self._mkts.query(
            query_embeddings=[self._embed(mkt_string)],
            n_results=min(top_k, self._mkts.count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        return self._to_search_results(results)

    # ── past_decisions ────────────────────────────────────────────────────────

    def add_decision(self, decision: dict[str, Any]) -> None:
        """Store a technical deviation ruling so future projects can learn from it."""
        text: str = decision["text"]
        doc_id: str = decision.get("id") or self._stable_id("decision", text)

        meta = {k: v for k, v in decision.items() if k not in ("id", "text")}
        meta.setdefault("added_at", str(date.today()))

        self._decisions.upsert(
            ids=[doc_id],
            embeddings=[self._embed(text)],
            documents=[text],
            metadatas=[meta],
        )

    def query_decisions(self, query: str, top_k: int = 3) -> list[SearchResult]:
        """Retrieve past rulings most relevant to a deviation description."""
        results = self._decisions.query(
            query_embeddings=[self._embed(query)],
            n_results=min(top_k, self._decisions.count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        return self._to_search_results(results)

    # ── product_specs ─────────────────────────────────────────────────────────

    def add_product_spec(
        self,
        product_name: str,
        spec_text: str,
        metadata: dict[str, Any],
    ) -> None:
        """Store manufacturer datasheet content for a product."""
        doc_id = self._stable_id("spec", product_name.lower())

        meta = {
            "product_name": product_name,
            "added_at": str(date.today()),
            **metadata,
        }

        self._specs.upsert(
            ids=[doc_id],
            embeddings=[self._embed(spec_text)],
            documents=[spec_text],
            metadatas=[meta],
        )

    def query_product_specs(self, query: str, top_k: int = 2) -> list[SearchResult]:
        """Retrieve spec content most relevant to a product query."""
        results = self._specs.query(
            query_embeddings=[self._embed(query)],
            n_results=min(top_k, self._specs.count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        return self._to_search_results(results)

    # ── shared result builder ─────────────────────────────────────────────────

    def _to_search_results(self, chroma_result: dict) -> list[SearchResult]:
        ids = chroma_result["ids"][0]
        docs = chroma_result["documents"][0]
        metas = chroma_result["metadatas"][0]
        scores = self._distances_to_scores(chroma_result["distances"][0])

        return [
            SearchResult(id=i, text=d, metadata=m, score=s)
            for i, d, m, s in zip(ids, docs, metas, scores)
        ]
