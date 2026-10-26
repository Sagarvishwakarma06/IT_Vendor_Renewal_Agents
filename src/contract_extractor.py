"""
contract_extractor.py
---------------------
Extracts structured contract terms from raw contract text using
regex-based pattern matching.

PURPOSE (English):
    This module takes the raw text returned by contract_reader.py and
    finds key fields: vendor name, dates, notice period, renewal type,
    SLA requirements, and annual cost.

    Because regex matching is NOT perfect, every field carries a
    confidence level (HIGH / MEDIUM / LOW / NOT_FOUND) and a snippet
    of the exact supporting text.  Ambiguous or conflicting findings
    are flagged for human review rather than silently guessed.

PURPOSE (Hindi):
    Yeh module contract ke raw text se important details nikalता hai:
    vendor ka naam, dates, notice period, SLA, aur cost.
    Har field ke saath confidence level aur source text hota hai.
    Agar kuch clear nahi hai, to human review ka warning aata hai -
    system kabhi silently galat assumption nahi karta.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------

class Confidence:
    HIGH = "HIGH"          # Unambiguous pattern match
    MEDIUM = "MEDIUM"      # Reasonable match, minor uncertainty
    LOW = "LOW"            # Weak or inferred match
    NOT_FOUND = "NOT_FOUND"  # No match found


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ExtractedField:
    """A single extracted field with its source evidence."""
    value: Optional[str]
    confidence: str
    evidence: str          # The exact text snippet that produced this value
    page_hint: str = ""    # Page hint if available (e.g., "page 2")

    def is_found(self) -> bool:
        return self.confidence != Confidence.NOT_FOUND and self.value is not None


@dataclass
class ContractTerms:
    """
    All structured fields extracted from one contract document.

    Attributes
    ----------
    source_file      : Filename of the source document.
    vendor_name      : Extracted vendor name.
    contract_start   : Contract start date (ISO string YYYY-MM-DD).
    contract_end     : Contract end date (ISO string YYYY-MM-DD).
    renewal_type     : e.g. "Automatic annual renewal" or "Manual renewal required".
    notice_period_days : Notice period in days (integer as string).
    notice_deadline  : Calculated deadline (ISO string).
    sla_terms        : List of extracted SLA clauses.
    annual_cost      : Annual renewal cost text.
    renewal_clause   : Full renewal clause text.
    missing_fields   : Fields that could not be found.
    warnings         : Human-review warnings.
    extraction_notes : Explanations of uncertain extractions.
    """
    source_file: str = ""
    vendor_name: ExtractedField = field(default_factory=lambda: ExtractedField(None, Confidence.NOT_FOUND, ""))
    contract_start: ExtractedField = field(default_factory=lambda: ExtractedField(None, Confidence.NOT_FOUND, ""))
    contract_end: ExtractedField = field(default_factory=lambda: ExtractedField(None, Confidence.NOT_FOUND, ""))
    renewal_type: ExtractedField = field(default_factory=lambda: ExtractedField(None, Confidence.NOT_FOUND, ""))
    notice_period_days: ExtractedField = field(default_factory=lambda: ExtractedField(None, Confidence.NOT_FOUND, ""))
    notice_deadline: ExtractedField = field(default_factory=lambda: ExtractedField(None, Confidence.NOT_FOUND, ""))
    sla_terms: list[str] = field(default_factory=list)
    annual_cost: ExtractedField = field(default_factory=lambda: ExtractedField(None, Confidence.NOT_FOUND, ""))
    renewal_clause: ExtractedField = field(default_factory=lambda: ExtractedField(None, Confidence.NOT_FOUND, ""))
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extraction_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to a plain dictionary for serialisation."""
        def ef(f: ExtractedField) -> dict:
            return {"value": f.value, "confidence": f.confidence, "evidence": f.evidence}
        return {
            "source_file": self.source_file,
            "vendor_name": ef(self.vendor_name),
            "contract_start": ef(self.contract_start),
            "contract_end": ef(self.contract_end),
            "renewal_type": ef(self.renewal_type),
            "notice_period_days": ef(self.notice_period_days),
            "notice_deadline": ef(self.notice_deadline),
            "sla_terms": self.sla_terms,
            "annual_cost": ef(self.annual_cost),
            "renewal_clause": ef(self.renewal_clause),
            "missing_fields": self.missing_fields,
            "warnings": self.warnings,
            "extraction_notes": self.extraction_notes,
        }


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Date patterns: "1 January 2024", "01/01/2024", "2024-01-01"
_MONTH_NAMES = (
    "january|february|march|april|may|june|july|august|"
    "september|october|november|december"
)
_DATE_PATTERNS = [
    # "1 January 2024" or "1st January 2024"
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + _MONTH_NAMES + r")\s+(\d{4})\b",
    # "January 1, 2024"
    r"\b(" + _MONTH_NAMES + r")\s+(\d{1,2}),?\s+(\d{4})\b",
    # ISO: "2024-01-01"
    r"\b(\d{4})-(\d{2})-(\d{2})\b",
    # "01/01/2024"
    r"\b(\d{2})/(\d{2})/(\d{4})\b",
]

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date_string(text: str) -> Optional[date]:
    """
    Try each date pattern and return the first successfully parsed date.
    Returns None if no date can be parsed.
    """
    text_lower = text.lower()

    # Pattern: "1 January 2024"
    m = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + _MONTH_NAMES + r")\s+(\d{4})\b",
        text_lower,
    )
    if m:
        try:
            return date(int(m.group(3)), _MONTH_MAP[m.group(2)], int(m.group(1)))
        except ValueError:
            pass

    # Pattern: "January 1, 2024"
    m = re.search(
        r"\b(" + _MONTH_NAMES + r")\s+(\d{1,2}),?\s+(\d{4})\b",
        text_lower,
    )
    if m:
        try:
            return date(int(m.group(3)), _MONTH_MAP[m.group(1)], int(m.group(2)))
        except ValueError:
            pass

    # ISO: "2024-01-01"
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # DD/MM/YYYY
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    return None


def _extract_context(text: str, match: re.Match, window: int = 120) -> str:
    """Return characters around a regex match as evidence text."""
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    snippet = text[start:end].replace("\n", " ").strip()
    return f"...{snippet}..."


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def _extract_vendor(text: str) -> ExtractedField:
    """Extract vendor name from standard contract header patterns."""
    patterns = [
        r"(?:Vendor|Licensor|Service Provider)\s*:\s*(.+?)(?:\n|$)",
        r"(?:between|by and between)\s+(.+?)\s+(?:and|&)\s+",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip().rstrip(".,;")
            if 3 <= len(val) <= 80:  # sanity length check
                return ExtractedField(
                    value=val,
                    confidence=Confidence.HIGH,
                    evidence=_extract_context(text, m, window=80),
                )
    return ExtractedField(None, Confidence.NOT_FOUND, "")


def _extract_dates(text: str) -> tuple[ExtractedField, ExtractedField]:
    """
    Extract contract start and end dates.
    Returns (start_field, end_field).
    """
    start_field = ExtractedField(None, Confidence.NOT_FOUND, "")
    end_field = ExtractedField(None, Confidence.NOT_FOUND, "")

    start_pattern = re.search(
        r"(?:Contract Start Date|Commencement Date|Start Date)\s*:\s*(.+?)(?:\n|$)",
        text, re.IGNORECASE
    )
    if start_pattern:
        d = _parse_date_string(start_pattern.group(1))
        if d:
            start_field = ExtractedField(
                value=d.isoformat(),
                confidence=Confidence.HIGH,
                evidence=_extract_context(text, start_pattern, 60),
            )

    end_pattern = re.search(
        r"(?:Contract End Date|Expiry Date|End Date|Termination Date)\s*:\s*(.+?)(?:\n|$)",
        text, re.IGNORECASE
    )
    if end_pattern:
        d = _parse_date_string(end_pattern.group(1))
        if d:
            end_field = ExtractedField(
                value=d.isoformat(),
                confidence=Confidence.HIGH,
                evidence=_extract_context(text, end_pattern, 60),
            )

    return start_field, end_field


def _extract_notice_period(text: str) -> ExtractedField:
    """Extract the notice period in days from contract text."""
    # "90 days" / "60-day" / "three months" etc.
    m = re.search(
        r"(?:Notice Period|notice of)\s*[:\s]*(\d+)\s*(?:-\s*)?days?",
        text, re.IGNORECASE
    )
    if m:
        return ExtractedField(
            value=m.group(1),
            confidence=Confidence.HIGH,
            evidence=_extract_context(text, m, 100),
        )

    # Try to find "X days prior to" style
    m = re.search(
        r"(\d+)\s*days?\s+(?:prior|before|in advance)",
        text, re.IGNORECASE
    )
    if m:
        return ExtractedField(
            value=m.group(1),
            confidence=Confidence.MEDIUM,
            evidence=_extract_context(text, m, 100),
        )

    return ExtractedField(None, Confidence.NOT_FOUND, "")


def _extract_renewal_type(text: str) -> ExtractedField:
    """Detect whether the contract renews automatically or manually."""
    auto_pattern = re.search(
        r"(?:automatically renew|auto.?renew|automatic renewal)",
        text, re.IGNORECASE
    )
    manual_pattern = re.search(
        r"(?:will NOT renew automatically|manual renewal|no automatic renewal|"
        r"must provide written notice of renewal)",
        text, re.IGNORECASE
    )

    if auto_pattern and manual_pattern:
        # Conflicting signals — flag for human review
        return ExtractedField(
            value="CONFLICTING — review required",
            confidence=Confidence.LOW,
            evidence="Both automatic and manual renewal language found. Human review required.",
        )
    if auto_pattern:
        return ExtractedField(
            value="Automatic renewal",
            confidence=Confidence.HIGH,
            evidence=_extract_context(text, auto_pattern, 100),
        )
    if manual_pattern:
        return ExtractedField(
            value="Manual renewal required",
            confidence=Confidence.HIGH,
            evidence=_extract_context(text, manual_pattern, 100),
        )

    return ExtractedField(None, Confidence.NOT_FOUND, "")


def _extract_sla_terms(text: str) -> list[str]:
    """Extract SLA requirement lines from the contract."""
    sla_lines = []
    # Match lines that look like SLA clauses
    for m in re.finditer(
        r"(?:Critical|High|Medium|Low)\s+(?:Severity\s+)?Incidents?\s*:.*",
        text, re.IGNORECASE
    ):
        sla_lines.append(m.group(0).strip())

    # Also grab the overall SLA target if present
    overall = re.search(
        r"SLA achievement target.*",
        text, re.IGNORECASE
    )
    if overall:
        sla_lines.append(overall.group(0).strip())

    return sla_lines


def _extract_annual_cost(text: str) -> ExtractedField:
    """Extract the most recent quoted annual renewal cost."""
    # Prefer lines containing "renewal" and a currency amount
    m = re.search(
        r"(?:Quoted renewal|renewal for Year\s*\d+)[^\n]*?"
        r"((?:GBP|USD|EUR|\$|£|€)\s*[\d,]+(?:\.\d+)?)",
        text, re.IGNORECASE
    )
    if m:
        return ExtractedField(
            value=m.group(1).replace(",", "").strip(),
            confidence=Confidence.HIGH,
            evidence=_extract_context(text, m, 80),
        )

    # Fall back to any currency amount on a line with "annual" or "cost"
    m = re.search(
        r"(?:annual|year\s*\d+)[^\n]*?((?:GBP|USD|EUR|\$|£|€)\s*[\d,]+(?:\.\d+)?)",
        text, re.IGNORECASE
    )
    if m:
        return ExtractedField(
            value=m.group(1).replace(",", "").strip(),
            confidence=Confidence.MEDIUM,
            evidence=_extract_context(text, m, 80),
        )

    return ExtractedField(None, Confidence.NOT_FOUND, "")


def _extract_renewal_clause(text: str) -> ExtractedField:
    """Extract the full renewal clause paragraph."""
    m = re.search(
        r"(?:RENEWAL CLAUSE|3\.\s+RENEWAL)[^\n]*\n((?:.+\n?){1,8})",
        text, re.IGNORECASE
    )
    if m:
        return ExtractedField(
            value=m.group(1).strip(),
            confidence=Confidence.HIGH,
            evidence=m.group(0).strip()[:400],
        )
    return ExtractedField(None, Confidence.NOT_FOUND, "")


def _calculate_notice_deadline(
    contract_end: ExtractedField,
    notice_period: ExtractedField,
) -> tuple[ExtractedField, list[str]]:
    """
    Calculate the notice deadline = contract_end_date - notice_period_days.
    Returns (deadline_field, warnings).
    """
    warnings: list[str] = []

    if not contract_end.is_found() or not notice_period.is_found():
        missing = []
        if not contract_end.is_found():
            missing.append("contract end date")
        if not notice_period.is_found():
            missing.append("notice period")
        warnings.append(
            f"Cannot calculate notice deadline — missing: {', '.join(missing)}."
        )
        return ExtractedField(None, Confidence.NOT_FOUND, ""), warnings

    try:
        end_date = date.fromisoformat(contract_end.value)
        days = int(notice_period.value)
        deadline = end_date - timedelta(days=days)
        today = date.today()
        days_remaining = (deadline - today).days

        if days_remaining < 0:
            warnings.append(
                f"URGENT: Notice deadline {deadline.isoformat()} has PASSED "
                f"({abs(days_remaining)} days ago). "
                "Contact legal/procurement immediately. "
                "A passed deadline does NOT mean the contract is automatically terminated — "
                "the legal position must be verified by qualified personnel."
            )
        elif days_remaining <= 30:
            warnings.append(
                f"URGENT: Notice deadline {deadline.isoformat()} is {days_remaining} day(s) away. "
                "Immediate attention required."
            )
        elif days_remaining <= 60:
            warnings.append(
                f"WARNING: Notice deadline {deadline.isoformat()} is {days_remaining} day(s) away."
            )

        return ExtractedField(
            value=deadline.isoformat(),
            confidence=Confidence.HIGH,
            evidence=(
                f"Calculated: {contract_end.value} - {days} days = {deadline.isoformat()}. "
                f"Days until deadline (from today {today.isoformat()}): {days_remaining}."
            ),
        ), warnings

    except (ValueError, TypeError) as exc:
        msg = f"Could not calculate notice deadline: {exc}"
        warnings.append(msg)
        return ExtractedField(None, Confidence.LOW, ""), warnings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_contract_terms(text: str, source_file: str = "") -> ContractTerms:
    """
    Extract structured contract terms from raw contract text.

    This function uses deterministic regex patterns — it does NOT use an LLM.
    Confidence levels indicate how reliable each extraction is.
    Missing or ambiguous fields are flagged in `missing_fields` and `warnings`.

    Parameters
    ----------
    text : str
        Raw text of the contract document (from contract_reader.read_contract).
    source_file : str
        Filename of the source document (for traceability).

    Returns
    -------
    ContractTerms
        Structured extraction with confidence levels and evidence.

    Notes
    -----
    - Fields with Confidence.NOT_FOUND or Confidence.LOW require human review.
    - Never treat NOT_FOUND as "no clause exists" — the clause may be present
      but use language not covered by the current patterns.
    """
    terms = ContractTerms(source_file=source_file)

    if not text or not text.strip():
        terms.warnings.append("Empty text supplied — no extraction possible.")
        terms.missing_fields = [
            "vendor_name", "contract_start", "contract_end",
            "renewal_type", "notice_period", "sla_terms", "annual_cost",
        ]
        return terms

    # Run each extraction
    terms.vendor_name = _extract_vendor(text)
    terms.contract_start, terms.contract_end = _extract_dates(text)
    terms.notice_period_days = _extract_notice_period(text)
    terms.renewal_type = _extract_renewal_type(text)
    terms.sla_terms = _extract_sla_terms(text)
    terms.annual_cost = _extract_annual_cost(text)
    terms.renewal_clause = _extract_renewal_clause(text)

    # Calculate notice deadline
    deadline_field, deadline_warnings = _calculate_notice_deadline(
        terms.contract_end, terms.notice_period_days
    )
    terms.notice_deadline = deadline_field
    terms.warnings.extend(deadline_warnings)

    # Identify missing fields
    field_checks = {
        "vendor_name": terms.vendor_name,
        "contract_start": terms.contract_start,
        "contract_end": terms.contract_end,
        "renewal_type": terms.renewal_type,
        "notice_period_days": terms.notice_period_days,
        "annual_cost": terms.annual_cost,
    }
    for fname, fval in field_checks.items():
        if not fval.is_found():
            terms.missing_fields.append(fname)

    if not terms.sla_terms:
        terms.missing_fields.append("sla_terms")

    # Add review warnings for low-confidence fields
    for fname, fval in field_checks.items():
        if fval.confidence == Confidence.LOW:
            terms.warnings.append(
                f"Field '{fname}' has LOW confidence extraction. "
                "Human review of the source document is required."
            )
        if fval.confidence == Confidence.MEDIUM:
            terms.extraction_notes.append(
                f"Field '{fname}' was inferred from context (MEDIUM confidence). "
                "Verify against the original document."
            )

    if terms.renewal_type.value == "CONFLICTING — review required":
        terms.warnings.append(
            "Conflicting renewal language detected (both automatic and manual). "
            "This requires immediate human review of the contract."
        )

    logger.info(
        "Extracted terms from '%s': %d missing fields, %d warnings",
        source_file,
        len(terms.missing_fields),
        len(terms.warnings),
    )

    return terms
