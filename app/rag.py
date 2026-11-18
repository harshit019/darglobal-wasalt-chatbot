"""Hybrid RAG retrieval engine (BM25 + TF-IDF cosine similarity + metadata boosting)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import Citation, KnowledgeDocSummary, KnowledgeStats, SourceName


TOKEN_RE = re.compile(r"[a-zA-Z0-9\u0600-\u06FF]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric + Arabic tokenizer."""
    return [tok.lower() for tok in TOKEN_RE.findall(text)]


@dataclass
class IndexedChunk:
    """A single retrievable passage derived from a scraped document."""

    chunk_id: str
    doc_id: str
    source: str  # "darglobal" | "wasalt"
    category: str
    title: str
    url: str
    location: str | None
    brand: str | None
    text: str
    searchable_text: str


class HybridRAGIndex:
    """In-memory hybrid search index over scraped DarGlobal and Wasalt documents."""

    def __init__(self, chunk_size: int = 900, chunk_overlap: int = 160) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.documents: list[dict[str, Any]] = []
        self.chunks: list[IndexedChunk] = []
        self.scraped_at: str = "unknown"

        self._bm25: BM25Okapi | None = None
        self._word_vectorizer: TfidfVectorizer | None = None
        self._word_matrix = None
        self._char_vectorizer: TfidfVectorizer | None = None
        self._char_matrix = None

    def load_from_file(self, path: Path) -> None:
        """Load scraped knowledge base JSON and build retrieval indexes."""
        if not path.exists():
            self.documents = []
            self.chunks = []
            self.scraped_at = "not-scraped"
            return

        payload = json.loads(path.read_text(encoding="utf-8"))
        self.scraped_at = payload.get("scraped_at", "unknown")
        self.documents = payload.get("documents", [])
        self._build_index()

    def _chunk_text(self, text: str) -> list[str]:
        """Split long document text into overlapping paragraph-aware chunks."""
        cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
        if len(cleaned) <= self.chunk_size:
            return [cleaned] if cleaned else []

        paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            if len(para) > self.chunk_size:
                if current:
                    chunks.append(current.strip())
                    current = ""
                start = 0
                while start < len(para):
                    end = start + self.chunk_size
                    chunks.append(para[start:end].strip())
                    start = max(end - self.chunk_overlap, start + 1)
                    if end >= len(para):
                        break
                continue

            if len(current) + len(para) + 2 <= self.chunk_size:
                current = f"{current}\n\n{para}" if current else para
            else:
                if current:
                    chunks.append(current.strip())
                tail = current[-self.chunk_overlap :] if current else ""
                current = f"{tail}\n\n{para}".strip() if tail else para

        if current:
            chunks.append(current.strip())

        return chunks

    def _build_index(self) -> None:
        """Chunk all documents and build BM25 + TF-IDF matrices."""
        chunks: list[IndexedChunk] = []

        for doc in self.documents:
            doc_id = str(doc.get("id", ""))
            source = str(doc.get("source", "darglobal")).lower()
            category = str(doc.get("category", "General"))
            title = str(doc.get("title", "Untitled")).strip()
            url = str(doc.get("url", "")).strip()
            location = doc.get("location")
            brand = doc.get("brand")
            content = str(doc.get("content", "")).strip()
            metadata_tags = doc.get("tags") or []

            header_parts = [
                f"Source: {'DarGlobal' if source == 'darglobal' else 'Wasalt'}",
                f"Title: {title}",
                f"Category: {category}",
            ]
            if location:
                header_parts.append(f"Location: {location}")
            if brand:
                header_parts.append(f"Brand / Partner: {brand}")
            if metadata_tags:
                header_parts.append(f"Tags: {', '.join(map(str, metadata_tags))}")
            header = " | ".join(header_parts)

            for idx, piece in enumerate(self._chunk_text(content)):
                searchable = f"{header}\n{piece}"
                chunks.append(
                    IndexedChunk(
                        chunk_id=f"{doc_id}::chunk_{idx}",
                        doc_id=doc_id,
                        source=source,
                        category=category,
                        title=title,
                        url=url,
                        location=location,
                        brand=brand,
                        text=piece,
                        searchable_text=searchable,
                    )
                )

        self.chunks = chunks
        if not chunks:
            self._bm25 = None
            self._word_vectorizer = None
            self._word_matrix = None
            self._char_vectorizer = None
            self._char_matrix = None
            return

        corpus_texts = [c.searchable_text for c in chunks]
        tokenized_corpus = [tokenize(t) for t in corpus_texts]
        self._bm25 = BM25Okapi(tokenized_corpus)

        self._word_vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,
            max_features=20000,
        )
        self._word_matrix = self._word_vectorizer.fit_transform(corpus_texts)

        self._char_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            sublinear_tf=True,
            max_features=25000,
        )
        self._char_matrix = self._char_vectorizer.fit_transform(corpus_texts)

    def retrieve(
        self,
        query: str,
        top_k: int = 6,
        source_filter: SourceName = "all",
    ) -> list[tuple[IndexedChunk, float]]:
        """Retrieve top-k relevant chunks using hybrid BM25 + TF-IDF + metadata signals."""
        if not self.chunks or self._bm25 is None:
            return []

        q_clean = query.strip()
        if not q_clean:
            return []

        q_tokens = tokenize(q_clean)
        q_lower = q_clean.lower()

        # 1. BM25 lexical scores
        bm25_raw = np.array(self._bm25.get_scores(q_tokens), dtype=float)
        bm25_max = float(bm25_raw.max()) if bm25_raw.size else 0.0
        bm25_norm = bm25_raw / bm25_max if bm25_max > 0 else np.zeros_like(bm25_raw)

        # 2. Word-level TF-IDF cosine similarity
        word_q = self._word_vectorizer.transform([q_clean])
        word_scores = cosine_similarity(word_q, self._word_matrix).ravel()

        # 3. Character n-gram TF-IDF cosine similarity (handles minor spelling/transliteration variants)
        char_q = self._char_vectorizer.transform([q_clean])
        char_scores = cosine_similarity(char_q, self._char_matrix).ravel()

        # Detect implicit source intent when user didn't filter explicitly
        mentions_dg = any(k in q_lower for k in ("darglobal", "dar global", "dar al arkan"))
        mentions_wasalt = "wasalt" in q_lower

        combined = 0.45 * bm25_norm + 0.40 * word_scores + 0.15 * char_scores

        # Metadata / title / entity boost
        for i, chunk in enumerate(self.chunks):
            if source_filter != "all" and chunk.source != source_filter:
                combined[i] = -1.0
                continue

            boost = 0.0
            title_lower = chunk.title.lower()
            if title_lower and title_lower in q_lower:
                boost += 0.35
            else:
                title_tokens = set(tokenize(title_lower))
                overlap = len(title_tokens.intersection(q_tokens))
                if overlap >= 2:
                    boost += 0.18
                elif overlap == 1 and len(title_tokens) <= 3:
                    boost += 0.08

            if chunk.location and chunk.location.lower() in q_lower:
                boost += 0.15
            if chunk.brand and chunk.brand.lower() in q_lower:
                boost += 0.18

            if source_filter == "all":
                if mentions_dg and not mentions_wasalt and chunk.source == "darglobal":
                    boost += 0.12
                elif mentions_wasalt and not mentions_dg and chunk.source == "wasalt":
                    boost += 0.12

            combined[i] += boost

        ranked_indices = np.argsort(combined)[::-1]

        results: list[tuple[IndexedChunk, float]] = []
        per_doc_counts: dict[str, int] = {}

        for idx in ranked_indices:
            score = float(combined[idx])
            if score <= 0.02:
                break
            chunk = self.chunks[int(idx)]
            # Keep diversity across documents (at most 2 chunks from the same doc)
            if per_doc_counts.get(chunk.doc_id, 0) >= 2:
                continue
            per_doc_counts[chunk.doc_id] = per_doc_counts.get(chunk.doc_id, 0) + 1
            results.append((chunk, round(score, 4)))
            if len(results) >= top_k:
                break

        # If query is very broad (e.g., "tell me about both companies"), ensure balanced overview
        if not results:
            fallback = [
                c
                for c in self.chunks
                if source_filter == "all" or c.source == source_filter
            ][:top_k]
            return [(c, 0.1) for c in fallback]

        return results

    def to_citations(self, hits: list[tuple[IndexedChunk, float]]) -> list[Citation]:
        """Deduplicate retrieved chunks into clean UI citations."""
        seen_urls: set[str] = set()
        citations: list[Citation] = []

        for chunk, score in hits:
            key = f"{chunk.source}::{chunk.title}::{chunk.url}"
            if key in seen_urls:
                continue
            seen_urls.add(key)
            snippet = chunk.text[:220].replace("\n", " ").strip()
            if len(chunk.text) > 220:
                snippet += "..."
            citations.append(
                Citation(
                    title=chunk.title,
                    url=chunk.url,
                    source=chunk.source,  # type: ignore[arg-type]
                    category=chunk.category,
                    snippet=snippet,
                    score=score,
                )
            )
        return citations

    def get_stats(self) -> KnowledgeStats:
        """Return summary statistics and document previews for the Knowledge Explorer."""
        dg_count = sum(1 for d in self.documents if d.get("source") == "darglobal")
        wasalt_count = sum(1 for d in self.documents if d.get("source") == "wasalt")
        categories: dict[str, int] = {}
        summaries: list[KnowledgeDocSummary] = []

        for doc in self.documents:
            cat = str(doc.get("category", "General"))
            categories[cat] = categories.get(cat, 0) + 1
            raw_content = str(doc.get("content", "")).replace("\n", " ").strip()
            summaries.append(
                KnowledgeDocSummary(
                    id=str(doc.get("id", "")),
                    source=doc.get("source", "darglobal"),
                    category=cat,
                    title=str(doc.get("title", "Untitled")),
                    url=str(doc.get("url", "")),
                    location=doc.get("location"),
                    brand=doc.get("brand"),
                    summary=(raw_content[:180] + "...") if len(raw_content) > 180 else raw_content,
                )
            )

        return KnowledgeStats(
            total_documents=len(self.documents),
            total_chunks=len(self.chunks),
            darglobal_documents=dg_count,
            wasalt_documents=wasalt_count,
            scraped_at=self.scraped_at,
            categories=categories,
            documents=summaries,
        )
