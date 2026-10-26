"""
Tests for agent safety guardrails — including spec test cases.
SPEC TEST 1: Missing contract
SPEC TEST 6: Termination request
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.agent import VendorRenewalAgent, check_forbidden_action


class TestForbiddenActions:
    """SPEC TEST 6: User says 'Terminate now' → advisory response only."""

    def test_terminate_now_blocked(self):
        response = check_forbidden_action("Terminate now")
        assert response is not None
        assert len(response) > 10
        assert "cannot" in response.lower() or "advisory" in response.lower()

    def test_cancel_contract_blocked(self):
        response = check_forbidden_action("Please cancel contract for VendorA")
        assert response is not None

    def test_auto_renew_blocked(self):
        response = check_forbidden_action("auto renew the agreement")
        assert response is not None

    def test_normal_query_allowed(self):
        response = check_forbidden_action("Show me the VendorA SLA performance")
        assert response is None or response == ""

    def test_recommendation_query_allowed(self):
        response = check_forbidden_action("What is the renewal recommendation for VendorA?")
        assert response is None or response == ""

    def test_agent_handle_user_input_terminate(self):
        agent = VendorRenewalAgent()
        msg = agent.handle_user_input("Terminate now")
        assert len(msg) > 0
        assert "cannot" in msg.lower() or "advisory" in msg.lower()


class TestMissingContract:
    """SPEC TEST 1: No contract available → clear error, do not invent terms."""

    def test_load_nonexistent_contract(self, tmp_path):
        agent = VendorRenewalAgent(data_dir="data")
        result = agent.load_contract(tmp_path / "missing_contract.txt")
        assert result["success"] is False
        assert "error" in result
        # Must NOT have invented contract terms
        assert "vendor_name" not in result or result.get("terms") is None

    def test_run_full_assessment_no_contract(self):
        """Running without a contract should not fabricate terms."""
        agent = VendorRenewalAgent(data_dir="data", output_dir="outputs")
        result = agent.run_full_assessment(
            vendor="VendorA",
            contract_file=None,
            evaluation_period="test",
            save=False,
        )
        contract_result = result.get("contract", {})
        assert contract_result.get("success") is False
        # Missing info must be recorded
        assert "contract document" in agent.state.missing_information


class TestAssessmentSave:
    """Tests for duplicate-safe saving."""

    def test_duplicate_save_blocked_by_default(self, tmp_path):
        from src.assessment_store import save_renewal_assessment
        data = {
            "vendor": "VendorTest",
            "evaluation_period": "2025",
            "assessment_id": "ASSESS-TEST-abc12345",
            "recommendation": "Renew",
        }
        # First save
        r1 = save_renewal_assessment(data, output_dir=tmp_path)
        assert r1["saved"] is True

        # Second save — same ID, should be blocked
        r2 = save_renewal_assessment(data, output_dir=tmp_path)
        assert r2["saved"] is False
        assert r2["duplicate_detected"] is True

    def test_duplicate_save_allowed_with_flag(self, tmp_path):
        from src.assessment_store import save_renewal_assessment
        data = {
            "vendor": "VendorTest",
            "evaluation_period": "2025",
            "assessment_id": "ASSESS-TEST-abc99999",
            "recommendation": "Renew",
        }
        r1 = save_renewal_assessment(data, output_dir=tmp_path)
        assert r1["saved"] is True
        r2 = save_renewal_assessment(data, output_dir=tmp_path, allow_overwrite=True)
        assert r2["saved"] is True

    def test_save_missing_required_fields(self, tmp_path):
        from src.assessment_store import save_renewal_assessment
        data = {"recommendation": "Renew"}  # missing vendor and evaluation_period
        result = save_renewal_assessment(data, output_dir=tmp_path)
        assert result["saved"] is False
        assert "required" in result["message"].lower()
