"""
deadline_monitor.py
-------------------
Monitors contract renewal notice deadlines.

PURPOSE (English):
    Given a contract end date and notice period (in days), calculates
    the notice deadline and how many days remain.
    Alerts are colour-coded: PASSED / URGENT / WARNING / OK.
    A passed deadline does NOT mean automatic renewal or termination —
    the legal position must always be verified by qualified personnel.

PURPOSE (Hindi):
    Contract end date aur notice period se deadline calculate karta hai.
    Kitne din baaki hain yeh batata hai.
    Passed deadline ka matlab automatic renewal ya termination NAHI hai —
    legal team se confirm karna zaroori hai.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alert levels
# ---------------------------------------------------------------------------

class AlertLevel:
    PASSED  = "PASSED"   # Deadline already gone
    URGENT  = "URGENT"   # <= urgent_days remaining
    WARNING = "WARNING"  # <= warning_days remaining
    OK      = "OK"       # Comfortably within deadline


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class DeadlineResult:
    """
    Notice deadline calculation result.

    Attributes
    ----------
    vendor              : Vendor name.
    contract_end        : Contract end date.
    notice_period_days  : Contractual notice period in days.
    notice_deadline     : Calculated deadline (contract_end - notice_days).
    days_until_deadline : Days from today to the deadline (negative if passed).
    alert_level         : PASSED / URGENT / WARNING / OK.
    alert_message       : Human-readable explanation.
    source_clause       : Exact text of the notice period clause (for traceability).
    calculation_note    : How the deadline was calculated.
    warnings            : Additional warnings (e.g. date uncertainty).
    errors              : Fatal calculation errors.
    """
    vendor: str
    contract_end: Optional[date] = None
    notice_period_days: Optional[int] = None
    notice_deadline: Optional[date] = None
    days_until_deadline: Optional[int] = None
    alert_level: str = AlertLevel.OK
    alert_message: str = ""
    source_clause: str = ""
    calculation_note: str = ""
    warnings: list = None
    errors: list = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_notice_deadline(
    vendor: str,
    contract_end_date: str | date,
    notice_period_days: int,
    *,
    reference_date: Optional[date] = None,
    urgent_days: int = 30,
    warning_days: int = 60,
    source_clause: str = "",
) -> DeadlineResult:
    """
    Calculate the notice deadline from the contract end date and notice period.

    Parameters
    ----------
    vendor : str
        Vendor name for reporting.
    contract_end_date : str or date
        Contract end date (ISO string "YYYY-MM-DD" or date object).
    notice_period_days : int
        Contractual notice period in whole days.
    reference_date : date, optional
        Date to calculate days remaining from (default: today).
        Override for testing.
    urgent_days : int
        Days-remaining threshold for URGENT alert (default 30).
    warning_days : int
        Days-remaining threshold for WARNING alert (default 60).
    source_clause : str
        The exact contract clause text for this notice period (evidence).

    Returns
    -------
    DeadlineResult

    Notes
    -----
    Convention: notice deadline = contract_end_date - notice_period_days.
    This means the vendor must receive written notice BY the deadline date
    to exercise a valid option. Verify with legal counsel in all cases.
    """
    result = DeadlineResult(vendor=vendor, source_clause=source_clause)

    # Parse contract end date
    if isinstance(contract_end_date, str):
        try:
            end_date = date.fromisoformat(contract_end_date)
        except ValueError as exc:
            result.errors.append(
                f"Invalid contract_end_date format '{contract_end_date}': {exc}. "
                "Use ISO format YYYY-MM-DD."
            )
            result.alert_level = AlertLevel.URGENT
            result.alert_message = "Could not calculate deadline — invalid date."
            return result
    else:
        end_date = contract_end_date

    # Validate notice period
    if not isinstance(notice_period_days, int) or notice_period_days < 0:
        result.errors.append(
            f"Invalid notice_period_days '{notice_period_days}'. "
            "Must be a non-negative integer."
        )
        return result

    today = reference_date or date.today()
    deadline = end_date - timedelta(days=notice_period_days)
    days_remaining = (deadline - today).days

    result.contract_end = end_date
    result.notice_period_days = notice_period_days
    result.notice_deadline = deadline
    result.days_until_deadline = days_remaining
    result.calculation_note = (
        f"Notice deadline = contract end date ({end_date.isoformat()}) "
        f"minus {notice_period_days} days notice period "
        f"= {deadline.isoformat()}. "
        f"Reference date: {today.isoformat()}. "
        f"Days until deadline: {days_remaining}."
    )

    # Set alert level
    if days_remaining < 0:
        result.alert_level = AlertLevel.PASSED
        result.alert_message = (
            f"PASSED: The notice deadline of {deadline.isoformat()} has passed "
            f"({abs(days_remaining)} day(s) ago). "
            "IMPORTANT: A passed deadline does NOT automatically renew or terminate this contract. "
            "The legal position is uncertain — contact your legal and procurement teams immediately."
        )
        result.warnings.append(result.alert_message)
    elif days_remaining <= urgent_days:
        result.alert_level = AlertLevel.URGENT
        result.alert_message = (
            f"URGENT: Notice deadline {deadline.isoformat()} is {days_remaining} day(s) away. "
            "Immediate action required. Contact legal/procurement today."
        )
        result.warnings.append(result.alert_message)
    elif days_remaining <= warning_days:
        result.alert_level = AlertLevel.WARNING
        result.alert_message = (
            f"WARNING: Notice deadline {deadline.isoformat()} is {days_remaining} day(s) away. "
            "Plan and initiate the renewal or replacement process promptly."
        )
    else:
        result.alert_level = AlertLevel.OK
        result.alert_message = (
            f"OK: Notice deadline {deadline.isoformat()} is {days_remaining} day(s) away. "
            "No immediate action required, but schedule a review."
        )

    logger.info(
        "Deadline for '%s': deadline=%s, days_remaining=%d, alert=%s",
        vendor, deadline.isoformat(), days_remaining, result.alert_level,
    )
    return result
