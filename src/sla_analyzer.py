"""
sla_analyzer.py
---------------
Evaluates vendor SLA performance from incident records.

PURPOSE (English):
    Compares each incident response time against the SLA target.
    Calculates: SLA Achievement % = incidents meeting SLA / eligible incidents x 100.
    Returns breach details, severity breakdowns, and evidence references.
    Handles zero eligible incidents safely (no divide-by-zero).

PURPOSE (Hindi):
    Har incident ka response time SLA target se compare karta hai.
    Achievement % = SLA meet karne wale incidents / total eligible x 100.
    Breach details aur severity breakdown deta hai.
    Zero incidents pe divide-by-zero error nahi aata.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class IncidentResult:
    """Result of evaluating a single incident."""
    incident_id: str
    vendor: str
    severity: str
    response_hours: float
    sla_hours: float
    met_sla: bool
    breach_by_hours: float  # Positive = breach, 0 = met exactly, negative = met early


@dataclass
class SeverityBreakdown:
    """SLA performance for a specific severity level."""
    severity: str
    total_incidents: int
    met_sla: int
    breached: int
    achievement_pct: Decimal
    breach_incident_ids: list[str]


@dataclass
class SLAResult:
    """
    Complete SLA performance evaluation for a vendor.

    Attributes
    ----------
    vendor                 : Vendor name.
    eligible_incidents     : Total incidents used in the calculation.
    met_sla_count          : Incidents that met the SLA target.
    breached_count         : Incidents that breached the SLA target.
    achievement_pct        : SLA achievement percentage.
    severity_breakdown     : Per-severity breakdown.
    breach_details         : List of breaching incidents with evidence.
    warnings               : Data quality and coverage warnings.
    errors                 : Fatal issues.
    status                 : "CALCULATED", "NO_DATA", or "ERROR"
    """
    vendor: str
    eligible_incidents: int = 0
    met_sla_count: int = 0
    breached_count: int = 0
    achievement_pct: Decimal = Decimal("0")
    severity_breakdown: dict[str, SeverityBreakdown] = field(default_factory=dict)
    breach_details: list[IncidentResult] = field(default_factory=list)
    all_results: list[IncidentResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = "NOT_RUN"
    recommendation_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_sla_performance(
    df: pd.DataFrame,
    vendor: str,
    *,
    severity_filter: Optional[list[str]] = None,
    sla_target_override: Optional[float] = None,
) -> SLAResult:
    """
    Evaluate SLA performance for a vendor from incident records.

    SLA Achievement (%) = Incidents Meeting SLA / Eligible Incidents x 100.

    An incident "meets SLA" when response_hours <= sla_hours.
    The sla_hours column in the data must reflect the contractual SLA target
    for each incident. If a uniform override target is needed for testing,
    supply sla_target_override.

    Parameters
    ----------
    df : pd.DataFrame
        Loaded incident data (from data_loader.load_incidents).
    vendor : str
        The vendor to evaluate.
    severity_filter : list[str], optional
        Restrict evaluation to specific severity levels.
        e.g. ["critical", "high"] to only evaluate high-priority incidents.
    sla_target_override : float, optional
        If supplied, use this single response-time target (hours) for all
        incidents instead of the per-incident sla_hours column.
        Use only for testing or when a single contractual target applies.

    Returns
    -------
    SLAResult

    Example
    -------
    >>> result = evaluate_sla_performance(df, "VendorA")
    >>> print(result.achievement_pct)
    71.43
    """
    result = SLAResult(vendor=vendor)

    if df.empty:
        result.status = "NO_DATA"
        result.errors.append("Incident DataFrame is empty.")
        return result

    required_cols = {"vendor", "incident_id", "severity", "response_hours", "sla_hours"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        result.status = "ERROR"
        result.errors.append(f"Missing columns: {sorted(missing_cols)}")
        return result

    # Filter to vendor
    vendor_df = df[df["vendor"].str.strip().str.lower() == vendor.strip().lower()].copy()
    if vendor_df.empty:
        result.status = "NO_DATA"
        result.warnings.append(f"No incident records found for vendor '{vendor}'.")
        return result

    # Apply severity filter
    if severity_filter:
        severity_filter_lower = [s.lower() for s in severity_filter]
        vendor_df = vendor_df[vendor_df["severity"].isin(severity_filter_lower)]
        if vendor_df.empty:
            result.status = "NO_DATA"
            result.warnings.append(
                f"No incidents for vendor '{vendor}' matching severities: {severity_filter}."
            )
            return result

    # Apply SLA target override if provided
    if sla_target_override is not None:
        vendor_df = vendor_df.copy()
        vendor_df["sla_hours"] = sla_target_override
        result.warnings.append(
            f"SLA target override applied: {sla_target_override}h for all incidents. "
            "Ensure this matches the contractual SLA for these severities."
        )

    # Evaluate each incident
    severity_data: dict[str, dict] = {}

    for _, row in vendor_df.iterrows():
        inc_id = str(row["incident_id"])
        sev = str(row["severity"])
        resp_h = float(row["response_hours"])
        sla_h = float(row["sla_hours"])

        met = resp_h <= sla_h
        breach_by = resp_h - sla_h  # positive = breach

        inc_result = IncidentResult(
            incident_id=inc_id,
            vendor=vendor,
            severity=sev,
            response_hours=resp_h,
            sla_hours=sla_h,
            met_sla=met,
            breach_by_hours=round(breach_by, 2),
        )
        result.all_results.append(inc_result)

        if not met:
            result.breach_details.append(inc_result)

        # Aggregate by severity
        if sev not in severity_data:
            severity_data[sev] = {"total": 0, "met": 0, "breached": 0, "breach_ids": []}
        severity_data[sev]["total"] += 1
        if met:
            severity_data[sev]["met"] += 1
        else:
            severity_data[sev]["breached"] += 1
            severity_data[sev]["breach_ids"].append(inc_id)

    # Build severity breakdown
    for sev, counts in severity_data.items():
        total = counts["total"]
        met = counts["met"]
        if total > 0:
            ach_pct = (Decimal(str(met)) / Decimal(str(total)) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            ach_pct = Decimal("0")

        result.severity_breakdown[sev] = SeverityBreakdown(
            severity=sev,
            total_incidents=total,
            met_sla=met,
            breached=counts["breached"],
            achievement_pct=ach_pct,
            breach_incident_ids=counts["breach_ids"],
        )

    # Overall achievement
    result.eligible_incidents = len(result.all_results)
    result.met_sla_count = sum(1 for r in result.all_results if r.met_sla)
    result.breached_count = result.eligible_incidents - result.met_sla_count

    if result.eligible_incidents == 0:
        result.status = "NO_DATA"
        result.warnings.append(
            "No eligible incidents found. SLA achievement is UNAVAILABLE — "
            "cannot divide by zero. This is not the same as 100% achievement."
        )
        return result

    result.achievement_pct = (
        Decimal(str(result.met_sla_count))
        / Decimal(str(result.eligible_incidents))
        * Decimal("100")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    result.status = "CALCULATED"

    # Recommendation notes
    ach_float = float(result.achievement_pct)
    if ach_float >= 95.0:
        result.recommendation_notes.append(
            f"{vendor}: SLA achievement {result.achievement_pct}% — strong performance."
        )
    elif ach_float >= 85.0:
        result.recommendation_notes.append(
            f"{vendor}: SLA achievement {result.achievement_pct}% — acceptable but below typical 95% target. "
            "Monitor breach trends."
        )
    else:
        result.recommendation_notes.append(
            f"{vendor}: SLA achievement {result.achievement_pct}% — below acceptable levels. "
            "Significant SLA breaches detected. Consider escalation or vendor replacement."
        )

    # Highlight critical breaches
    critical_breaches = [
        r for r in result.breach_details if r.severity in ("critical", "high")
    ]
    if critical_breaches:
        ids = [r.incident_id for r in critical_breaches]
        result.warnings.append(
            f"Critical/High severity SLA breaches detected: {ids}. "
            "These incidents require immediate review."
        )

    logger.info(
        "SLA evaluation for '%s': %d eligible, %d met, %d breached, achievement %.2f%%",
        vendor,
        result.eligible_incidents,
        result.met_sla_count,
        result.breached_count,
        result.achievement_pct,
    )
    return result
