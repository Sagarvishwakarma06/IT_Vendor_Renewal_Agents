"""
utilisation.py
--------------
Calculates software licence utilisation rates.

PURPOSE (English):
    Formula: Utilisation (%) = Active Licences / Purchased Licences x 100.
    Calculates per-row, per-vendor monthly, and evaluation-period averages.
    Handles zero purchased licences safely (no division error).
    Uses a configurable low-utilisation threshold (default 70%).

PURPOSE (Hindi):
    Formula: Utilisation (%) = Active / Purchased x 100.
    Har row, vendor, aur month ke liye calculate karta hai.
    Zero purchased licences pe division error nahi aata.
    Low utilisation threshold configurable hai (default 70%).
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

logger = logging.getLogger(__name__)

# Configurable threshold — not a universal industry standard.
DEFAULT_LOW_UTILISATION_THRESHOLD: float = 70.0


@dataclass
class MonthlyUtilisation:
    """Utilisation result for a single vendor-month row."""
    vendor: str
    month: str
    licences_purchased: int
    licences_active: int
    utilisation_pct: Decimal
    is_low: bool
    note: str = ""


@dataclass
class UtilisationResult:
    """
    Complete utilisation analysis for one or more vendors.

    Attributes
    ----------
    monthly_rows       : Per-row utilisation calculations.
    vendor_summaries   : Vendor-level average utilisation over the period.
    period_average_pct : Overall average across all eligible rows.
    low_threshold_pct  : The threshold used (configurable).
    skipped_rows       : Rows that were skipped (e.g. zero purchased licences).
    warnings           : Non-fatal data quality issues.
    errors             : Fatal issues that prevented calculation.
    """
    monthly_rows: list[MonthlyUtilisation] = field(default_factory=list)
    vendor_summaries: dict[str, dict] = field(default_factory=dict)
    period_average_pct: Decimal = Decimal("0")
    low_threshold_pct: float = DEFAULT_LOW_UTILISATION_THRESHOLD
    skipped_rows: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recommendation_notes: list[str] = field(default_factory=list)


def calculate_utilisation_rate(
    df: pd.DataFrame,
    vendor: str | None = None,
    months: list[str] | None = None,
    low_threshold_pct: float = DEFAULT_LOW_UTILISATION_THRESHOLD,
) -> UtilisationResult:
    """
    Calculate licence utilisation rates from a usage DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Loaded usage data (from data_loader.load_usage).
    vendor : str, optional
        Filter to a specific vendor. If None, calculates for all vendors.
    months : list[str], optional
        Filter to specific months (e.g. ["2025-01", "2025-02"]).
        If None, uses all available months.
    low_threshold_pct : float
        Configurable low-utilisation alert threshold (default 70%).
        This threshold is for advisory purposes only, not an industry standard.

    Returns
    -------
    UtilisationResult
        Contains monthly rows, vendor summaries, and recommendation notes.

    Example
    -------
    >>> result = calculate_utilisation_rate(df, vendor="VendorA")
    >>> print(result.vendor_summaries["VendorA"]["average_utilisation_pct"])
    62.33
    """
    result = UtilisationResult(low_threshold_pct=low_threshold_pct)

    if df.empty:
        result.errors.append("Input DataFrame is empty — no utilisation can be calculated.")
        return result

    required_cols = {"vendor", "month", "licences_purchased", "licences_active"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        result.errors.append(f"Missing columns in usage data: {sorted(missing_cols)}")
        return result

    # Apply filters
    working = df.copy()
    if vendor:
        working = working[working["vendor"].str.strip().str.lower() == vendor.strip().lower()]
        if working.empty:
            result.errors.append(f"No data found for vendor '{vendor}'.")
            return result

    if months:
        working = working[working["month"].isin(months)]
        if working.empty:
            result.errors.append(f"No data found for months: {months}.")
            return result

    # Process each row
    all_util_pcts: list[Decimal] = []

    for _, row in working.iterrows():
        purchased = int(row["licences_purchased"])
        active = int(row["licences_active"])
        vendor_name = str(row["vendor"])
        month = str(row["month"])

        if purchased == 0:
            result.skipped_rows.append({
                "vendor": vendor_name,
                "month": month,
                "reason": "licences_purchased is 0 — division undefined.",
            })
            result.warnings.append(
                f"Skipped {vendor_name} / {month}: licences_purchased = 0."
            )
            continue

        # Core calculation — using Decimal for financial precision
        util_pct = Decimal(str(active)) / Decimal(str(purchased)) * Decimal("100")
        util_pct = util_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        is_low = float(util_pct) < low_threshold_pct
        note = ""
        if is_low:
            over_purchased = purchased - active
            note = (
                f"Utilisation below {low_threshold_pct}% threshold. "
                f"{over_purchased} licence(s) unused. Consider renegotiating quantity."
            )

        row_result = MonthlyUtilisation(
            vendor=vendor_name,
            month=month,
            licences_purchased=purchased,
            licences_active=active,
            utilisation_pct=util_pct,
            is_low=is_low,
            note=note,
        )
        result.monthly_rows.append(row_result)
        all_util_pcts.append(util_pct)

    if not all_util_pcts:
        result.errors.append(
            "No eligible rows after filtering — cannot calculate utilisation."
        )
        return result

    # Vendor-level summaries
    vendor_rows: dict[str, list[Decimal]] = {}
    for mr in result.monthly_rows:
        vendor_rows.setdefault(mr.vendor, []).append(mr.utilisation_pct)

    for v, pcts in vendor_rows.items():
        avg = sum(pcts) / len(pcts)
        avg = avg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        is_low_avg = float(avg) < low_threshold_pct
        summary = {
            "vendor": v,
            "months_analysed": len(pcts),
            "average_utilisation_pct": avg,
            "min_pct": min(pcts),
            "max_pct": max(pcts),
            "is_low_average": is_low_avg,
        }
        result.vendor_summaries[v] = summary

        if is_low_avg:
            result.recommendation_notes.append(
                f"{v}: Average utilisation {avg}% is below the {low_threshold_pct}% threshold. "
                "This suggests potential over-purchasing. "
                "Renegotiating licence quantities or pricing may reduce costs. "
                "Note: utilisation alone does not determine the recommendation — "
                "SLA performance, cost, and contract terms must also be considered."
            )
        else:
            result.recommendation_notes.append(
                f"{v}: Average utilisation {avg}% is at or above the {low_threshold_pct}% threshold."
            )

    # Overall period average
    result.period_average_pct = (
        (sum(all_util_pcts) / len(all_util_pcts))
        .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    logger.info(
        "Utilisation calculated: %d rows, period average %.2f%%",
        len(result.monthly_rows),
        result.period_average_pct,
    )
    return result
