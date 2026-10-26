"""
test_report_generator.py
-------------------------
Unit tests for src/report_generator.py.
Verifies Markdown and HTML executive report creation, table generation,
and sign-off blocks.
"""

import pytest
from src.report_generator import generate_executive_markdown, generate_executive_html
from src.agent import VendorRenewalAgent


@pytest.fixture
def sample_assessment():
    agent = VendorRenewalAgent(data_dir="data", output_dir="outputs")
    res = agent.run_full_assessment(
        vendor="VendorA",
        contract_file="data/contracts/VendorA_Contract.txt",
        evaluation_period="2025-H1",
        save=False,
    )
    return res


class TestReportGenerator:
    def test_generate_executive_markdown(self, sample_assessment):
        md = generate_executive_markdown(sample_assessment)
        assert isinstance(md, str)
        assert len(md) > 500
        assert "# IT VENDOR RENEWAL DECISION PACKAGE" in md
        assert "Options Comparison Matrix" in md
        assert "Formal Governance & Sign-Off Authorization" in md
        assert "Chief Information Officer" in md
        assert "LEGAL DISCLAIMER" in md

    def test_generate_executive_html(self, sample_assessment):
        html = generate_executive_html(sample_assessment)
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "<title>IT Vendor Renewal Assessment" in html
        assert "VendorA" in html
        assert "Options Comparison Matrix" in html

    def test_empty_assessment_graceful_handling(self):
        empty_dict = {}
        md = generate_executive_markdown(empty_dict)
        assert "Unknown Vendor" in md
        assert "Options Comparison Matrix" in md
