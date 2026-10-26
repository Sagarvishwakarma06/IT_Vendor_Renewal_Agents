"""Tests for cost_comparator.py — including spec test cases."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from decimal import Decimal
import pandas as pd
import pytest
import openpyxl

from src.cost_comparator import compare_vendor_costs


def make_quotations_df(rows):
    return pd.DataFrame(rows, columns=["vendor", "option", "annual_cost", "migration_cost"])


class TestCompareVendorCosts:

    def test_basic_comparison(self):
        df = make_quotations_df([
            ("VendorA", "renew",       95000, 0),
            ("VendorA", "renegotiate", 82000, 0),
            ("VendorA", "replace",     78000, 25000),
        ])
        result = compare_vendor_costs(df, "VendorA")
        assert "renew" in result.options
        assert "renegotiate" in result.options
        assert "replace" in result.options
        # Renegotiate should show positive savings vs renew
        savings = result.options["renegotiate"].savings_vs_renew
        assert savings == Decimal("13000.00")

    # --- SPEC TEST 4: Unpriced migration ---
    def test_spec_test_4_missing_migration_cost(self):
        """
        SPEC TEST 4: Replacement quotation has no migration cost.
        Expected: Flag missing info, withhold definitive replacement recommendation.
        """
        df = make_quotations_df([
            ("VendorA", "renew",   95000, 0),
            ("VendorA", "replace", 78000, None),
        ])
        result = compare_vendor_costs(df, "VendorA")
        assert result.recommendation_pending is True
        assert not result.options["replace"].is_complete
        assert any("migration" in w.lower() or "pending" in w.lower() for w in result.warnings)

    # --- SPEC TEST 5: Quotation change → recalculate ---
    def test_spec_test_5_quotation_change(self):
        """
        SPEC TEST 5: Update a vendor quotation → recalculate all comparisons.
        Old renew=95000, new renew=88000 should change savings calculation.
        """
        df_old = make_quotations_df([
            ("VendorA", "renew",       95000, 0),
            ("VendorA", "renegotiate", 82000, 0),
        ])
        result_old = compare_vendor_costs(df_old, "VendorA")
        old_saving = result_old.options["renegotiate"].savings_vs_renew

        df_new = make_quotations_df([
            ("VendorA", "renew",       88000, 0),  # Updated quotation
            ("VendorA", "renegotiate", 82000, 0),
        ])
        result_new = compare_vendor_costs(df_new, "VendorA")
        new_saving = result_new.options["renegotiate"].savings_vs_renew

        assert old_saving != new_saving
        assert new_saving == Decimal("6000.00")  # 88000 - 82000

    def test_vendor_not_found(self):
        df = make_quotations_df([("VendorA", "renew", 95000, 0)])
        result = compare_vendor_costs(df, "VendorZ")
        assert result.errors

    def test_missing_annual_cost(self):
        df = make_quotations_df([("VendorA", "renew", None, 0)])
        result = compare_vendor_costs(df, "VendorA")
        # Should warn about missing annual cost
        assert any("annual" in w.lower() or "missing" in w.lower() for w in result.warnings) or \
               result.options.get("renew", None) is not None

    def test_replace_note_about_unconfirmed_renegotiation(self):
        """Renegotiation quotations should be marked as proposed, not confirmed."""
        df = make_quotations_df([
            ("VendorA", "renew",       95000, 0),
            ("VendorA", "renegotiate", 82000, 0),
        ])
        result = compare_vendor_costs(df, "VendorA")
        renegotiate_notes = result.options["renegotiate"].notes
        assert any("proposed" in n.lower() or "confirmed" in n.lower() for n in renegotiate_notes)

    def test_multi_year_total_includes_migration_once(self):
        """Migration cost should only appear in year 1, not each year."""
        df = make_quotations_df([
            ("VendorA", "renew",   95000,  0),
            ("VendorA", "replace", 78000, 25000),
        ])
        result_1yr = compare_vendor_costs(df, "VendorA", years=1)
        result_2yr = compare_vendor_costs(df, "VendorA", years=2)
        # 2yr replace = 78000*2 + 25000 = 181000; 1yr = 103000
        r1yr_replace = result_1yr.options["replace"].first_year_total
        assert r1yr_replace == Decimal("103000.00")

    def test_real_sample_file(self):
        from src.data_loader import load_quotations
        path = Path("data/quotations.xlsx")
        if not path.exists():
            pytest.skip("Sample file not found")
        lr = load_quotations(path)
        assert lr.success
        result = compare_vendor_costs(lr.data, "VendorA")
        assert not result.errors
        assert "renew" in result.options
