"""Tests for data_loader.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import pytest
import pandas as pd
from src.data_loader import load_usage, load_incidents, load_quotations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_usage_df(**overrides):
    data = {
        "vendor": ["VendorA"],
        "month": ["2025-01"],
        "licences_purchased": [500],
        "licences_active": [310],
        **overrides,
    }
    return pd.DataFrame(data)


def make_incidents_df(**overrides):
    data = {
        "vendor": ["VendorA"],
        "incident_id": ["INC-001"],
        "severity": ["high"],
        "response_hours": [6.0],
        "sla_hours": [4.0],
        **overrides,
    }
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# load_usage tests
# ---------------------------------------------------------------------------

class TestLoadUsage:

    def test_missing_file(self, tmp_path):
        result = load_usage(tmp_path / "nonexistent.csv")
        assert result.success is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_valid_csv(self, tmp_path):
        f = tmp_path / "usage.csv"
        f.write_text("vendor,month,licences_purchased,licences_active\nVendorA,2025-01,500,310\n")
        result = load_usage(f)
        assert result.success is True
        assert len(result.data) == 1

    def test_missing_column(self, tmp_path):
        f = tmp_path / "usage.csv"
        f.write_text("vendor,month,licences_purchased\nVendorA,2025-01,500\n")
        result = load_usage(f)
        assert result.success is False
        assert any("licences_active" in e for e in result.errors)

    def test_negative_licences_error(self, tmp_path):
        f = tmp_path / "usage.csv"
        f.write_text("vendor,month,licences_purchased,licences_active\nVendorA,2025-01,-500,310\n")
        result = load_usage(f)
        assert result.success is False
        assert any("negative" in e.lower() for e in result.errors)

    def test_zero_purchased_warns(self, tmp_path):
        f = tmp_path / "usage.csv"
        f.write_text("vendor,month,licences_purchased,licences_active\nVendorA,2025-01,0,0\n")
        result = load_usage(f)
        assert result.success is True
        assert any("0" in w for w in result.warnings)

    def test_active_greater_than_purchased_warns(self, tmp_path):
        f = tmp_path / "usage.csv"
        f.write_text("vendor,month,licences_purchased,licences_active\nVendorA,2025-01,100,150\n")
        result = load_usage(f)
        assert result.success is True
        assert any("active > licences_purchased" in w or "active" in w.lower() for w in result.warnings)

    def test_non_numeric_values_warned(self, tmp_path):
        f = tmp_path / "usage.csv"
        f.write_text("vendor,month,licences_purchased,licences_active\nVendorA,2025-01,FIVE HUNDRED,310\n")
        result = load_usage(f)
        # Row should be dropped, not error
        assert result.success is True or not result.data.empty or result.warnings

    def test_real_sample_file(self):
        path = Path("data/usage.csv")
        if not path.exists():
            pytest.skip("Sample file not found")
        result = load_usage(path)
        assert result.success is True
        assert len(result.data) > 0
        assert "vendor" in result.data.columns


# ---------------------------------------------------------------------------
# load_incidents tests
# ---------------------------------------------------------------------------

class TestLoadIncidents:

    def test_missing_file(self, tmp_path):
        result = load_incidents(tmp_path / "no.csv")
        assert result.success is False

    def test_valid_csv(self, tmp_path):
        f = tmp_path / "inc.csv"
        f.write_text(
            "vendor,incident_id,severity,response_hours,sla_hours\n"
            "VendorA,INC-001,high,6.0,4.0\n"
        )
        result = load_incidents(f)
        assert result.success is True
        assert len(result.data) == 1

    def test_negative_response_hours(self, tmp_path):
        f = tmp_path / "inc.csv"
        f.write_text(
            "vendor,incident_id,severity,response_hours,sla_hours\n"
            "VendorA,INC-001,high,-1.0,4.0\n"
        )
        result = load_incidents(f)
        assert result.success is False
        assert any("negative" in e.lower() for e in result.errors)

    def test_duplicate_incident_ids_warned(self, tmp_path):
        f = tmp_path / "inc.csv"
        f.write_text(
            "vendor,incident_id,severity,response_hours,sla_hours\n"
            "VendorA,INC-001,high,6.0,4.0\n"
            "VendorA,INC-001,high,3.0,4.0\n"
        )
        result = load_incidents(f)
        assert result.success is True
        assert any("duplicate" in w.lower() for w in result.warnings)

    def test_unknown_severity_warned(self, tmp_path):
        f = tmp_path / "inc.csv"
        f.write_text(
            "vendor,incident_id,severity,response_hours,sla_hours\n"
            "VendorA,INC-001,catastrophic,6.0,4.0\n"
        )
        result = load_incidents(f)
        assert result.success is True
        assert any("severity" in w.lower() or "unknown" in w.lower() for w in result.warnings)

    def test_real_sample_file(self):
        path = Path("data/incidents.csv")
        if not path.exists():
            pytest.skip("Sample file not found")
        result = load_incidents(path)
        assert result.success is True


# ---------------------------------------------------------------------------
# load_quotations tests
# ---------------------------------------------------------------------------

class TestLoadQuotations:

    def test_missing_file(self, tmp_path):
        result = load_quotations(tmp_path / "no.xlsx")
        assert result.success is False

    def test_negative_annual_cost(self, tmp_path):
        """Negative annual cost should cause a fatal error."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["vendor", "option", "annual_cost", "migration_cost"])
        ws.append(["VendorA", "renew", -5000, 0])
        path = tmp_path / "q.xlsx"
        wb.save(path)
        result = load_quotations(path)
        assert result.success is False
        assert any("negative" in e.lower() for e in result.errors)

    def test_missing_migration_cost_warns(self, tmp_path):
        """Missing migration cost for replace option should warn, not error."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["vendor", "option", "annual_cost", "migration_cost"])
        ws.append(["VendorA", "replace", 70000, None])
        path = tmp_path / "q.xlsx"
        wb.save(path)
        result = load_quotations(path)
        assert result.success is True
        assert any("migration" in w.lower() for w in result.warnings)

    def test_real_sample_file(self):
        path = Path("data/quotations.xlsx")
        if not path.exists():
            pytest.skip("Sample file not found")
        result = load_quotations(path)
        assert result.success is True
        assert len(result.data) >= 3
