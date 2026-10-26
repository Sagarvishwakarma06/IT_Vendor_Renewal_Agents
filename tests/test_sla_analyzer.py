"""Tests for sla_analyzer.py — including spec test cases."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from decimal import Decimal
import pandas as pd
import pytest

from src.sla_analyzer import evaluate_sla_performance


def make_incidents_df(rows):
    return pd.DataFrame(rows, columns=["vendor", "incident_id", "severity", "response_hours", "sla_hours"])


class TestEvaluateSlaPerformance:

    # --- SPEC TEST 3: SLA breach ---
    def test_spec_test_3_high_severity_breach(self):
        """
        SPEC TEST 3: A high-severity incident took 6 hours against a 4-hour target.
        Expected: Count the breach, identify incident and SLA target.
        """
        df = make_incidents_df([
            ("VendorA", "INC-001", "high", 6.0, 4.0),
        ])
        result = evaluate_sla_performance(df, "VendorA")
        assert result.status == "CALCULATED"
        assert result.breached_count == 1
        assert result.met_sla_count == 0
        assert result.achievement_pct == Decimal("0.00")
        # Breach should be identified with the incident ID
        assert "INC-001" in [r.incident_id for r in result.breach_details]

    def test_sla_met_incident(self):
        """An incident meeting the SLA target should be counted as met."""
        df = make_incidents_df([("VendorA", "INC-001", "high", 3.5, 4.0)])
        result = evaluate_sla_performance(df, "VendorA")
        assert result.met_sla_count == 1
        assert result.breached_count == 0
        assert result.achievement_pct == Decimal("100.00")

    def test_sla_met_exactly_on_boundary(self):
        """Responding exactly at the SLA limit counts as meeting it."""
        df = make_incidents_df([("VendorA", "INC-001", "critical", 2.0, 2.0)])
        result = evaluate_sla_performance(df, "VendorA")
        assert result.met_sla_count == 1

    def test_no_eligible_incidents_returns_no_data(self):
        """
        Zero eligible incidents must return NO_DATA status — not 100% or 0%.
        This is explicitly not a divide-by-zero error.
        """
        df = make_incidents_df([])
        result = evaluate_sla_performance(df, "VendorA")
        assert result.status == "NO_DATA"
        assert result.eligible_incidents == 0

    def test_vendor_not_found_returns_no_data(self):
        df = make_incidents_df([("VendorA", "INC-001", "high", 3.5, 4.0)])
        result = evaluate_sla_performance(df, "VendorZ")
        assert result.status == "NO_DATA"

    def test_severity_breakdown(self):
        """Multiple severities should be broken down separately."""
        df = make_incidents_df([
            ("VendorA", "INC-001", "critical", 1.5, 2.0),  # met
            ("VendorA", "INC-002", "high",     6.0, 4.0),  # breached
            ("VendorA", "INC-003", "medium",   3.5, 8.0),  # met
        ])
        result = evaluate_sla_performance(df, "VendorA")
        assert "critical" in result.severity_breakdown
        assert "high" in result.severity_breakdown
        assert result.severity_breakdown["high"].breached == 1
        assert result.severity_breakdown["critical"].met_sla == 1

    def test_severity_filter(self):
        """Severity filter should restrict evaluation to specified levels."""
        df = make_incidents_df([
            ("VendorA", "INC-001", "critical", 1.5, 2.0),
            ("VendorA", "INC-002", "low", 100.0, 48.0),  # breach but excluded
        ])
        result = evaluate_sla_performance(df, "VendorA", severity_filter=["critical"])
        assert result.eligible_incidents == 1

    def test_sla_target_override(self):
        """A uniform SLA override should replace per-row sla_hours."""
        df = make_incidents_df([("VendorA", "INC-001", "high", 6.0, 100.0)])
        # Without override: 6 <= 100 → met
        r1 = evaluate_sla_performance(df, "VendorA")
        assert r1.met_sla_count == 1

        # With override = 4h: 6 > 4 → breached
        r2 = evaluate_sla_performance(df, "VendorA", sla_target_override=4.0)
        assert r2.breached_count == 1
        assert any("override" in w.lower() for w in r2.warnings)

    def test_critical_breach_generates_warning(self):
        """Critical severity breaches should generate a warning."""
        df = make_incidents_df([("VendorA", "INC-001", "critical", 5.0, 2.0)])
        result = evaluate_sla_performance(df, "VendorA")
        assert any("INC-001" in w for w in result.warnings)

    def test_real_sample_data(self):
        """Integration: evaluate SLA for VendorA from sample data."""
        from src.data_loader import load_incidents
        path = Path("data/incidents.csv")
        if not path.exists():
            pytest.skip("Sample file not found")
        lr = load_incidents(path)
        assert lr.success
        result = evaluate_sla_performance(lr.data, "VendorA")
        assert result.status == "CALCULATED"
        assert result.eligible_incidents > 0
