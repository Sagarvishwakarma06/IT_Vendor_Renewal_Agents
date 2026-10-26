"""
cost_comparator.py
------------------
Compares renewal, renegotiation, and replacement cost options.

PURPOSE (English):
    Reads quotation data and calculates first-year and multi-year costs
    for renew, renegotiate, and replace options.
    Migration costs are included only when the data supplies them.
    Missing migration costs block the replacement recommendation.

PURPOSE (Hindi):
    Quotation data se renew, renegotiate, aur replace ke costs compare
    karta hai. Migration cost missing hone par replacement recommendation
    rok di jaati hai - incomplete data pe recommendation nahi deta.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OptionCost:
    """Cost breakdown for a single option (renew / renegotiate / replace)."""
    option: str
    annual_cost: Optional[Decimal]
    migration_cost: Optional[Decimal]   # None = not supplied (different from zero)
    first_year_total: Optional[Decimal]
    savings_vs_renew: Optional[Decimal]
    savings_pct_vs_renew: Optional[Decimal]
    is_complete: bool   # False if any required cost is missing
    missing_costs: list[str]
    assumptions: list[str]
    notes: list[str]


@dataclass
class CostComparisonResult:
    """
    Complete cost comparison for a vendor across all three options.

    Attributes
    ----------
    vendor            : Vendor name.
    options           : Dict of option name -> OptionCost.
    baseline_option   : The option used as the savings baseline (usually "renew").
    warnings          : Missing cost and data quality warnings.
    errors            : Fatal issues preventing comparison.
    recommendation_pending : True if replacement cannot be assessed due to missing costs.
    """
    vendor: str
    options: dict[str, OptionCost] = field(default_factory=dict)
    baseline_option: str = "renew"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recommendation_pending: bool = False
    recommendation_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        out = {"vendor": self.vendor, "baseline": self.baseline_option, "options": {}}
        for opt, oc in self.options.items():
            out["options"][opt] = {
                "annual_cost": str(oc.annual_cost) if oc.annual_cost is not None else None,
                "migration_cost": str(oc.migration_cost) if oc.migration_cost is not None else "NOT SUPPLIED",
                "first_year_total": str(oc.first_year_total) if oc.first_year_total is not None else None,
                "savings_vs_renew": str(oc.savings_vs_renew) if oc.savings_vs_renew is not None else None,
                "savings_pct_vs_renew": str(oc.savings_pct_vs_renew) if oc.savings_pct_vs_renew is not None else None,
                "is_complete": oc.is_complete,
                "missing_costs": oc.missing_costs,
                "assumptions": oc.assumptions,
                "notes": oc.notes,
            }
        out["warnings"] = self.warnings
        out["errors"] = self.errors
        out["recommendation_pending"] = self.recommendation_pending
        out["recommendation_notes"] = self.recommendation_notes
        return out


def compare_vendor_costs(
    df: pd.DataFrame,
    vendor: str,
    years: int = 1,
    *,
    annual_cost_increase_pct: float = 0.0,
    baseline_option: str = "renew",
) -> CostComparisonResult:
    """
    Compare renew, renegotiate, and replace cost options for a vendor.

    First-year total = annual_cost + migration_cost (one-time).
    Multi-year total = (annual_cost * years, with optional annual increase) + migration_cost.

    Parameters
    ----------
    df : pd.DataFrame
        Loaded quotation data (from data_loader.load_quotations).
    vendor : str
        The vendor to compare.
    years : int
        Number of years for multi-year comparison (default 1 = first-year only).
    annual_cost_increase_pct : float
        Annual cost increase % for multi-year projections.
        Must be made explicit — never applied silently.
    baseline_option : str
        Option used as the savings baseline (default "renew").

    Returns
    -------
    CostComparisonResult

    Notes
    -----
    - If migration_cost is None (not supplied) for the replace option, the
      replacement assessment is marked as PENDING.
    - Proposed renegotiation quotations are NOT treated as confirmed offers
      unless the source data documents their confirmed status.
    - Any price-increase assumptions are explicitly noted.
    """
    result = CostComparisonResult(vendor=vendor, baseline_option=baseline_option)

    if df.empty:
        result.errors.append("Quotation DataFrame is empty.")
        return result

    required_cols = {"vendor", "option", "annual_cost", "migration_cost"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        result.errors.append(f"Missing columns in quotation data: {sorted(missing_cols)}")
        return result

    vendor_df = df[df["vendor"].str.strip().str.lower() == vendor.strip().lower()].copy()
    if vendor_df.empty:
        result.errors.append(f"No quotation data found for vendor '{vendor}'.")
        return result

    if years < 1:
        result.errors.append("'years' parameter must be >= 1.")
        return result

    if annual_cost_increase_pct != 0.0 and years > 1:
        result.warnings.append(
            f"Annual cost increase of {annual_cost_increase_pct}% applied to years 2+. "
            "This is an assumption — verify against actual contract terms."
        )

    # Build OptionCost for each row
    baseline_annual: Optional[Decimal] = None

    for _, row in vendor_df.iterrows():
        opt = str(row["option"]).strip().lower()
        missing_costs: list[str] = []
        assumptions: list[str] = []
        notes: list[str] = []

        # Annual cost
        if pd.isna(row["annual_cost"]):
            annual_cost = None
            missing_costs.append("annual_cost")
        else:
            annual_cost = Decimal(str(row["annual_cost"])).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Migration cost
        if pd.isna(row["migration_cost"]):
            migration_cost = None
            if opt == "replace":
                missing_costs.append("migration_cost")
                notes.append(
                    "Migration cost not supplied. Replacement recommendation is PENDING. "
                    "Request a migration cost estimate before making a decision."
                )
        else:
            migration_cost = Decimal(str(row["migration_cost"])).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # First-year total
        if annual_cost is not None:
            mc = migration_cost if migration_cost is not None else Decimal("0")
            first_year = annual_cost + mc
        else:
            first_year = None

        # Multi-year calculation (only if annual_cost known)
        if annual_cost is not None and years > 1:
            assumptions.append(
                f"Multi-year projection over {years} years with "
                f"{annual_cost_increase_pct}% annual increase from year 2."
            )
            # Year 1: annual_cost + migration_cost
            # Years 2+: annual_cost * (1 + rate)^(n-1) each year
            mc = migration_cost if migration_cost is not None else Decimal("0")
            total = annual_cost + mc
            running = annual_cost
            for yr in range(2, years + 1):
                running = running * (1 + Decimal(str(annual_cost_increase_pct)) / 100)
                total += running.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            first_year = total  # repurposed as "multi-year total" here
            notes.append(f"Multi-year total shown for {years} years.")

        is_complete = len(missing_costs) == 0

        if opt == "renegotiate":
            notes.append(
                "Renegotiation quotation — treat as proposed, not confirmed, "
                "unless the source document confirms acceptance."
            )

        option_cost = OptionCost(
            option=opt,
            annual_cost=annual_cost,
            migration_cost=migration_cost,
            first_year_total=first_year,
            savings_vs_renew=None,  # calculated after all options collected
            savings_pct_vs_renew=None,
            is_complete=is_complete,
            missing_costs=missing_costs,
            assumptions=assumptions,
            notes=notes,
        )
        result.options[opt] = option_cost

        if opt == baseline_option and annual_cost is not None:
            baseline_annual = annual_cost

    # Calculate savings vs baseline
    baseline_opt = result.options.get(baseline_option)
    baseline_total = baseline_opt.first_year_total if baseline_opt else None

    for opt, oc in result.options.items():
        if opt == baseline_option:
            oc.savings_vs_renew = Decimal("0")
            oc.savings_pct_vs_renew = Decimal("0")
            continue

        if oc.first_year_total is not None and baseline_total is not None:
            saving = baseline_total - oc.first_year_total
            oc.savings_vs_renew = saving
            if baseline_total != 0:
                oc.savings_pct_vs_renew = (saving / baseline_total * 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

    # Replacement pending check
    replace_opt = result.options.get("replace")
    if replace_opt and not replace_opt.is_complete:
        result.recommendation_pending = True
        result.warnings.append(
            "REPLACEMENT ASSESSMENT PENDING: Migration cost is unknown. "
            "A definitive replacement recommendation cannot be made until the "
            "migration cost is supplied and the total cost is verified."
        )

    # Recommendation notes
    opts_by_cost = sorted(
        [(k, v) for k, v in result.options.items() if v.first_year_total is not None],
        key=lambda x: x[1].first_year_total,
    )
    if opts_by_cost:
        cheapest_name, cheapest = opts_by_cost[0]
        if cheapest_name == "replace" and result.recommendation_pending:
            result.recommendation_notes.append(
                "Replacement appears cheapest on annual cost alone but migration cost is unknown. "
                "Complete cost data is required before this option can be recommended."
            )
        elif cheapest.savings_vs_renew is not None and cheapest.savings_vs_renew > 0:
            result.recommendation_notes.append(
                f"'{cheapest_name}' has the lowest first-year cost "
                f"(saving {cheapest.savings_vs_renew} vs '{baseline_option}'). "
                "This is a cost-only finding — SLA, utilisation, and contract terms must also be considered."
            )

    logger.info(
        "Cost comparison for '%s': %d options, recommendation_pending=%s",
        vendor, len(result.options), result.recommendation_pending,
    )
    return result
