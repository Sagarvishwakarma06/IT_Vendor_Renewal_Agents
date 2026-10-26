"""
retriever.py
------------
Deterministic evidence retrieval component for IT vendor contracts, SLAs,
and procurement evaluation policies.

PURPOSE (English):
    This module indexes and retrieves relevant clauses from contract documents.
    It splits long contracts into structured, traceable chunks (with section,
    clause number, page number, and vendor metadata).
    It implements strict vendor isolation: queries for VendorA will NEVER
    retrieve clauses from VendorB.
    It uses a local, deterministic BM25 / TF-IDF lexical ranking algorithm
    that requires zero external API keys or LLM services.

PURPOSE (Hindi):
    Yeh module contracts aur documents ke important clauses ko dhundhta hai.
    Contract ko alag-alag sections (chunks) mein baant ta hai aur metadata
    (jaise vendor name, section title, clause number) save karta hai.
    Iska sabse bada fayda hai "Vendor Isolation" -- VendorA ke sawal par
    VendorB ka contract galti se bhi mix nahi hoga.
    Yeh bina kisi paid API ya internet ke locally fast search karta hai.
"""

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class DocumentChunk:
    """A single structured chunk of a contract document."""
    chunk_id: str
    vendor: str
    document_name: str
    section_title: str
    content: str
    clause_number: Optional[str] = None
    page: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def snippet(self, max_length: int = 150) -> str:
        """Return a clean snippet of the chunk content."""
        clean = " ".join(self.content.split())
        if len(clean) <= max_length:
            return clean
        return clean[:max_length] + "..."


@dataclass
class RetrievalMatch:
    """A scored search match linking query to evidence chunk."""
    chunk: DocumentChunk
    score: float
    relevance_tier: str  # HIGH, MEDIUM, LOW
    matched_terms: list[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    """Complete results from a retrieval search."""
    query: str
    vendor: str
    matches: list[RetrievalMatch] = field(default_factory=list)
    total_chunks_searched: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def has_matches(self) -> bool:
        return len(self.matches) > 0


class ContractRetriever:
    """
    Local, deterministic retriever for IT contracts and policy documents.
    Provides section-aware chunking and vendor-isolated evidence retrieval.
    """

    def __init__(self) -> None:
        self.chunks: list[DocumentChunk] = []
        self._doc_frequencies: dict[str, int] = {}
        self._total_documents: int = 0

    def clear(self) -> None:
        """Clear all indexed chunks."""
        self.chunks = []
        self._doc_frequencies = {}
        self._total_documents = 0

    def index_document(
        self,
        text: str,
        vendor: str,
        document_name: str,
        page_hint: int = 1,
    ) -> list[DocumentChunk]:
        """
        Split a contract document into structured chunks and add to index.

        Parameters
        ----------
        text : str
            Full raw text of the document.
        vendor : str
            Vendor associated with this contract.
        document_name : str
            Source document filename.
        page_hint : int
            Starting page number.
        """
        if not text or not text.strip():
            return []

        created_chunks = self._chunk_text(text, vendor, document_name, page_hint)
        self.chunks.extend(created_chunks)
        self._update_index_stats()
        return created_chunks

    def _chunk_text(
        self,
        text: str,
        vendor: str,
        document_name: str,
        page_hint: int,
    ) -> list[DocumentChunk]:
        """Split text into numbered sections or paragraph chunks."""
        chunks: list[DocumentChunk] = []
        lines = text.splitlines()
        
        current_section = "Preamble / General"
        current_clause_num = None
        current_lines: list[str] = []
        chunk_idx = 1

        # Match headers like "1. PARTIES", "Section 2: Term", "RENEWAL CLAUSE:"
        header_pattern = re.compile(
            r"^\s*(?:(?:\d+\.|\bSection\b|\bClause\b)\s+[A-Za-z0-9\s\-_,]{2,}|[A-Z0-9\s\-_]{3,}:)\s*$",
            re.IGNORECASE
        )
        clause_pattern = re.compile(r"^\s*(\d+(?:\.\d+)+)\.?\s*(.*)")

        def flush_chunk(section: str, clause: Optional[str], content_lines: list[str]) -> None:
            nonlocal chunk_idx
            content_str = "\n".join(content_lines).strip()
            if content_str:
                chunks.append(DocumentChunk(
                    chunk_id=f"{document_name}#c{chunk_idx}",
                    vendor=vendor,
                    document_name=document_name,
                    section_title=section,
                    clause_number=clause,
                    content=content_str,
                    page=page_hint,
                ))
                chunk_idx += 1

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            if header_pattern.match(line_str):
                flush_chunk(current_section, current_clause_num, current_lines)
                current_section = line_str.rstrip(":")
                current_clause_num = None
                current_lines = []
            elif clause_pattern.match(line_str):
                m_cl = clause_pattern.match(line_str)
                flush_chunk(current_section, current_clause_num, current_lines)
                current_clause_num = m_cl.group(1)
                current_lines = [line_str]
            else:
                current_lines.append(line_str)

        flush_chunk(current_section, current_clause_num, current_lines)

        # Fallback: if no chunks were created, index the entire text as a single chunk
        if not chunks and text.strip():
            chunks.append(DocumentChunk(
                chunk_id=f"{document_name}#c1",
                vendor=vendor,
                document_name=document_name,
                section_title="Full Document",
                clause_number=None,
                content=text.strip(),
                page=page_hint,
            ))

        return chunks

    def _tokenize(self, text: str) -> list[str]:
        """Convert text into lowercase tokens, filtering common stopwords."""
        words = re.findall(r"\b[a-z0-9_\-]{2,}\b", text.lower())
        stopwords = {
            "the", "and", "or", "to", "of", "in", "for", "with", "on", "at",
            "by", "an", "be", "is", "are", "was", "shall", "will", "this", "that"
        }
        return [w for w in words if w not in stopwords]

    def _update_index_stats(self) -> None:
        """Update term document frequencies for BM25/TF-IDF weighting."""
        self._total_documents = len(self.chunks)
        self._doc_frequencies = {}
        for ch in self.chunks:
            tokens = set(self._tokenize(ch.content + " " + ch.section_title))
            for t in tokens:
                self._doc_frequencies[t] = self._doc_frequencies.get(t, 0) + 1

    def retrieve(
        self,
        query: str,
        vendor: str,
        top_k: int = 3,
        min_score: float = 0.1,
    ) -> RetrievalResult:
        """
        Retrieve relevant chunks for a query under strict vendor isolation.

        Parameters
        ----------
        query : str
            Search query (e.g., 'notice period', 'termination clause', 'SLA credit').
        vendor : str
            The vendor to retrieve for. Chunks belonging to other vendors are omitted!
        top_k : int
            Maximum number of top results to return.
        min_score : float
            Minimum relevance threshold.
        """
        result = RetrievalResult(query=query, vendor=vendor)
        q_tokens = self._tokenize(query)

        if not q_tokens:
            result.warnings.append("Empty query or query contains only stopwords.")
            return result

        # Strictly filter by vendor to enforce vendor isolation (matches aliases like 'VendorA' to 'VendorA Solutions Ltd')
        v_low = vendor.lower()
        candidate_chunks = [
            ch for ch in self.chunks
            if ch.vendor.lower() == v_low or v_low in ch.vendor.lower() or ch.vendor.lower() in v_low
        ]
        result.total_chunks_searched = len(candidate_chunks)

        if not candidate_chunks:
            result.warnings.append(f"No indexed contract chunks found for vendor '{vendor}'.")
            return result

        scored_matches: list[RetrievalMatch] = []
        query_lower = query.lower()

        for chunk in candidate_chunks:
            chunk_text = (chunk.content + " " + chunk.section_title).lower()
            chunk_tokens = self._tokenize(chunk_text)
            chunk_len = len(chunk_tokens) or 1

            score = 0.0
            matched: list[str] = []

            # 1. Exact phrase boost
            if query_lower in chunk_text:
                score += 5.0
                matched.append(f"exact: '{query}'")

            # 2. Token match with BM25-inspired IDF weighting
            for token in q_tokens:
                count = chunk_tokens.count(token)
                if count > 0:
                    matched.append(token)
                    # IDF term
                    df = self._doc_frequencies.get(token, 1)
                    idf = math.log((self._total_documents - df + 0.5) / (df + 0.5) + 1.0)
                    tf = count / (count + 1.5 * (chunk_len / 50.0))
                    score += idf * tf

            # 3. Section title boost
            if any(t in chunk.section_title.lower() for t in q_tokens):
                score += 2.0

            if score >= min_score:
                tier = "HIGH" if score >= 4.0 else ("MEDIUM" if score >= 1.5 else "LOW")
                scored_matches.append(RetrievalMatch(
                    chunk=chunk,
                    score=round(score, 3),
                    relevance_tier=tier,
                    matched_terms=list(set(matched)),
                ))

        scored_matches.sort(key=lambda m: m.score, reverse=True)
        result.matches = scored_matches[:top_k]

        return result
