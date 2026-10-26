"""
test_retriever.py
-----------------
Unit tests for src/retriever.py.
Verifies chunking, vendor isolation, BM25 scoring, and agent integration.
"""

import pytest
from src.retriever import ContractRetriever, DocumentChunk
from src.agent import VendorRenewalAgent


class TestRetrieverChunking:
    def test_chunking_creates_traceable_chunks(self):
        text = """
        1. PARTIES
        This Agreement is between VendorA Solutions Ltd and Contoso.
        2. TERM AND TERMINATION
        Contract Start Date: 1 January 2024. Expiry: 31 December 2026.
        3. RENEWAL CLAUSE
        Notice Period: 90 days. This Agreement automatically renews annually.
        """
        retriever = ContractRetriever()
        chunks = retriever.index_document(text, vendor="VendorA", document_name="VendorA.txt")
        assert len(chunks) >= 3
        assert any("PARTIES" in c.section_title for c in chunks)
        assert any("RENEWAL" in c.section_title for c in chunks)
        assert all(c.vendor == "VendorA" for c in chunks)

    def test_empty_document_handling(self):
        retriever = ContractRetriever()
        chunks = retriever.index_document("", vendor="VendorA", document_name="empty.txt")
        assert chunks == []


class TestRetrieverVendorIsolation:
    def test_vendor_isolation_prevents_cross_vendor_leakage(self):
        """CRITICAL: Queries for VendorA must NEVER return VendorB clauses."""
        retriever = ContractRetriever()
        retriever.index_document(
            "RENEWAL CLAUSE: VendorA requires 90 days notice for renewal.",
            vendor="VendorA",
            document_name="VendorA.txt"
        )
        retriever.index_document(
            "RENEWAL CLAUSE: VendorB requires 60 days notice and manual confirmation.",
            vendor="VendorB",
            document_name="VendorB.txt"
        )

        res_a = retriever.retrieve("notice", vendor="VendorA")
        assert res_a.has_matches is True
        for m in res_a.matches:
            assert m.chunk.vendor == "VendorA"
            assert "VendorB" not in m.chunk.content

        res_b = retriever.retrieve("notice", vendor="VendorB")
        assert res_b.has_matches is True
        for m in res_b.matches:
            assert m.chunk.vendor == "VendorB"
            assert "VendorA" not in m.chunk.content

    def test_unknown_vendor_returns_warning(self):
        retriever = ContractRetriever()
        retriever.index_document("Content for Alpha", vendor="Alpha", document_name="alpha.txt")
        res = retriever.retrieve("Content", vendor="NonExistentVendor")
        assert len(res.matches) == 0
        assert any("No indexed contract chunks" in w for w in res.warnings)


class TestRetrieverScoringAndRanking:
    def test_exact_phrase_boost(self):
        retriever = ContractRetriever()
        retriever.index_document(
            "Section 1: General provisions.\n"
            "Section 2: The Service credits apply if SLA achievement falls below 90% in any calendar quarter.\n"
            "Section 3: Miscellaneous boilerplate clauses.\n",
            vendor="VendorA",
            document_name="doc.txt"
        )
        res = retriever.retrieve("Service credits", vendor="VendorA")
        assert res.has_matches is True
        top_match = res.matches[0]
        assert "Service credits" in top_match.chunk.content
        assert top_match.score >= 5.0

    def test_stopword_query_handled(self):
        retriever = ContractRetriever()
        retriever.index_document("Some clause content", vendor="VendorA", document_name="doc.txt")
        res = retriever.retrieve("the and or", vendor="VendorA")
        assert res.has_matches is False
        assert any("stopwords" in w for w in res.warnings)


class TestAgentRetrieverIntegration:
    def test_agent_search_contract_workflow(self):
        agent = VendorRenewalAgent(data_dir="data")
        agent.load_contract("data/contracts/VendorA_Contract.txt")
        agent.state.vendor = "VendorA Solutions Ltd"

        res = agent.search_contract("SLA achievement target")
        assert res["vendor"] == "VendorA Solutions Ltd"
        assert len(res["matches"]) > 0
        assert any("95" in m["content"] or "SLA" in m["content"] for m in res["matches"])
