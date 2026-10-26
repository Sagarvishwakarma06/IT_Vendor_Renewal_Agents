"""Tests for utilisation.py — including the mandatory test cases from the spec."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from decimal import Decimal
import pandas as pd
import pytest

from src.utilisation import calculate_utilisation_rate


def make_df(rows):
    return pd.DataFrame(rows, columns=["vendor", "month", "licences_purchased", "licences_active"])


class TestCalculateUtilisationRate:

    # --- SPEC TEST 2: 310 active out of 500 purchased = 62% ---
    def test_spec_test_2_low_utilisation(self):
        """
        SPEC TEST 2: 310 / 500 = 62%. Expect renegotiation note.
        """
        df = make_df([("VendorA", "2025-01", 500, 310)])
        result = calculate_utilisation_rate(df, vendor="VendorA")
        assert result.monthly_rows[0].utilisation_pct == Decimal("62.00")
        assert result.monthly_rows[0].is_low is True
        assert any("renegotiating" in n.lower() or "renegotiate" in n.lower()
                   for n in result.recommendation_notes)

    def test_normal_utilisation_not_flagged(self):
        df = make_df([("VendorA", "2025-01", 200, 188)])
        result = calculate_utilisation_rate(df, vendor="VendorA")
        assert result.monthly_rows[0].is_low is False
        assert float(result.monthly_rows[0].utilisation_pct) >= 70.0

    def test_zero_purchased_skipped(self):
        """
        Zero purchased licences must not cause division by zero.
        The row should be skipped with a warning.
        """
        df = make_df([("VendorA", "2025-01", 0, 0)])
        result = calculate_utilisation_rate(df, vendor="VendorA")
        assert len(result.monthly_rows) == 0
        assert len(result.skipped_rows) == 1
        assert any("0" in w for w in result.warnings)

    def test_100_percent_utilisation(self):
        df = make_df([("VendorA", "2025-01", 100, 100)])
        result = calculate_utilisation_rate(df, vendor="VendorA")
        assert result.monthly_rows[0].utilisation_pct == Decimal("100.00")
        assert result.monthly_rows[0].is_low is False

    def test_empty_dataframe_returns_error(self):
        result = calculate_utilisation_rate(pd.DataFrame())
        assert result.errors

    def test_vendor_not_found_returns_error(self):
        df = make_df([("VendorA", "2025-01", 500, 310)])
        result = calculate_utilisation_rate(df, vendor="VendorZ")
        assert result.errors

    def test_configurable_threshold(self):
        """Using a custom threshold should change the is_low flag."""
        df = make_df([("VendorA", "2025-01", 500, 310)])
        # 62% — below default 70% → low
        result_default = calculate_utilisation_rate(df, vendor="VendorA", low_threshold_pct=70.0)
        assert result_default.monthly_rows[0].is_low is True

        # With threshold 60%, 62% is above → NOT low
        result_custom = calculate_utilisation_rate(df, vendor="VendorA", low_threshold_pct=60.0)
        assert result_custom.monthly_rows[0].is_low is False

    def test_multi_month_average(self):
        df = make_df([
            ("VendorA", "2025-01", 500, 310),  # 62%
            ("VendorA", "2025-02", 500, 330),  # 66%
        ])
        result = calculate_utilisation_rate(df, vendor="VendorA")
        avg = result.vendor_summaries["VendorA"]["average_utilisation_pct"]
        assert avg == Decimal("64.00")

    def test_month_filter(self):
        df = make_df([
            ("VendorA", "2025-01", 500, 310),
            ("VendorA", "2025-02", 500, 330),
        ])
        result = calculate_utilisation_rate(df, vendor="VendorA", months=["2025-01"])
        assert len(result.monthly_rows) == 1

    def test_real_sample_data(self):
        """Integration: load the real CSV and calculate for VendorA."""
        from src.data_loader import load_usage
        path = Path("data/usage.csv")
        if not path.exists():
            pytest.skip("Sample file not found")
        lr = load_usage(path)
        assert lr.success
        result = calculate_utilisation_rate(lr.data, vendor="VendorA")
        assert not result.errors
        assert result.period_average_pct > 0
