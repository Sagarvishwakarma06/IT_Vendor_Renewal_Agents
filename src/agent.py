"""
agent.py
--------
The main IT Vendor Renewal Decision Support Agent.

PURPOSE (English):
    This module ties all tools together.
    It reads contracts, loads data, runs calculations, and generates
    an evidence-backed advisory recommendation.
    It cannot renew, terminate, sign, or modify contracts.
    All recommendations require human approval.

PURPOSE (Hindi):
    Yeh module sabhi tools ko ek jagah jodta hai.
    Contract padhta hai, data load karta hai, calculations karta hai,
    aur evidence-based advisory recommendation deta hai.
    Yeh contracts renew, terminate, sign, ya modify NAHI kar sakta.
    Sabhi recommendations ke liye human approval zaroori hai.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional, Any

from src.contract_reader import read_contract
from src.contract_extractor import extract_contract_terms, ContractTerms
from src.data_loader import load_usage, load_incidents, load_quotations
from src.utilisation import calculate_utilisation_rate, UtilisationResult
from src.sla_analyzer import evaluate_sla_performance, SLAResult
from src.cost_comparator import compare_vendor_costs, CostComparisonResult
from src.deadline_monitor import calculate_notice_deadline, DeadlineResult, AlertLevel
from src.assessment_store import save_renewal_assessment
from src.retriever import ContractRetriever

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Forbidden action safeguard
# ---------------------------------------------------------------------------

FORBIDDEN_ACTIONS = {
    "terminate", "cancel", "renew", "sign", "modify", "execute",
    "confirm", "approve contract", "send notice", "auto-renew",
}

TERMINATION_KEYWORDS = [
    "terminate now", "terminate contract", "terminate immediately", "terminate agreement",
    "cancel contract", "cancel the contract", "cancel agreement",
    "auto renew", "auto-renew", "sign contract", "execute contract",
    "send termination", "renew automatically", "approve renewal",
]

def check_forbidden_action(user_input: str) -> Optional[str]:
    """
    Check if the user is requesting a forbidden autonomous action.

    Returns an advisory message if forbidden, None otherwise.
    """
    lower = user_input.lower()
    for kw in TERMINATION_KEYWORDS:
        if kw in lower:
            return (
                "⛔ ADVISORY SYSTEM LIMIT: This agent cannot perform contractual actions "
                "such as termination, renewal, cancellation, or signing. "
                "It is an advisory tool only.\n\n"
                "What I can do:\n"
                "- Summarise the relevant contract terms and deadlines.\n"
                "- Show the notice period and whether it has passed.\n"
                "- Calculate the cost and SLA implications.\n"
                "- Produce an assessment for your legal and procurement teams.\n\n"
                "Required next step: Contact your legal counsel and procurement team "
                "to review the contract and initiate any formal action."
            )
    return None


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    """Holds all evaluation data for one vendor assessment session."""
    vendor: str = ""
    evaluation_period: str = ""
    contract_file: str = ""
    business_requirements: list[str] = field(default_factory=list)

    # Results from each tool
    contract_terms: Optional[ContractTerms] = None
    utilisation_result: Optional[UtilisationResult] = None
    sla_result: Optional[SLAResult] = None
    cost_result: Optional[CostComparisonResult] = None
    deadline_result: Optional[DeadlineResult] = None

    # Aggregated findings
    warnings: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recommendation: str = ""
    executive_summary: str = ""


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

class VendorRenewalAgent:
    """
    IT Vendor Renewal Decision Support Agent.

    Orchestrates contract reading, data loading, and analytical tools
    to produce an evidence-backed advisory recommendation.

    This agent is read-only and advisory. It will not execute contracts.
    """

    def __init__(
        self,
        data_dir: str | Path = "data",
        output_dir: str | Path = "outputs",
    ) -> None:
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.state = AgentState()
        self.retriever = ContractRetriever()

    # ------------------------------------------------------------------
    # Safe input check
    # ------------------------------------------------------------------

    def handle_user_input(self, user_input: str) -> str:
        """
        Check for forbidden actions before processing any user request.
        Returns an advisory message if the action is blocked.
        """
        guard = check_forbidden_action(user_input)
        if guard:
            logger.warning("Forbidden action requested: %s", user_input[:80])
            return guard
        return ""

    # ------------------------------------------------------------------
    # Step 1: Read contract
    # ------------------------------------------------------------------

    def load_contract(self, contract_file: str | Path) -> dict[str, Any]:
        """Read and extract terms from a contract document."""
        result = read_contract(contract_file)
        if not result.success:
            self.state.errors.append(
                f"Contract not available: {result.error}. "
                "Please supply the contract document to proceed."
            )
            self.state.missing_information.append("contract document")
            return {
                "success": False,
                "error": result.error,
                "warnings": result.warnings,
            }

        self.state.warnings.extend(result.warnings)

        # Extract structured terms
        terms = extract_contract_terms(result.text, source_file=str(contract_file))
        self.state.contract_terms = terms
        self.state.contract_file = str(contract_file)

        if terms.vendor_name.is_found() and not self.state.vendor:
            self.state.vendor = terms.vendor_name.value

        self.state.warnings.extend(terms.warnings)
        self.state.missing_information.extend(terms.missing_fields)

        # Index contract chunks into local retriever
        vendor_for_idx = terms.vendor_name.value or self.state.vendor or Path(contract_file).stem
        self.retriever.index_document(
            text=result.text,
            vendor=vendor_for_idx,
            document_name=Path(contract_file).name,
        )

        return {
            "success": True,
            "terms": terms.to_dict(),
            "warnings": terms.warnings,
            "missing_fields": terms.missing_fields,
        }

    def search_contract(self, query: str, top_k: int = 3) -> dict[str, Any]:
        """
        Retrieve relevant contract clauses for a query with strict vendor isolation.

        Parameters
        ----------
        query : str
            Search query (e.g., 'termination', 'liability', 'service credit').
        top_k : int
            Maximum number of top results to return.
        """
        vendor = self.state.vendor or "Unknown"
        res = self.retriever.retrieve(query, vendor=vendor, top_k=top_k)
        return {
            "query": res.query,
            "vendor": res.vendor,
            "total_chunks_searched": res.total_chunks_searched,
            "matches": [
                {
                    "chunk_id": m.chunk.chunk_id,
                    "section": m.chunk.section_title,
                    "clause": m.chunk.clause_number,
                    "content": m.chunk.content,
                    "score": m.score,
                    "relevance": m.relevance_tier,
                    "snippet": m.chunk.snippet(),
                }
                for m in res.matches
            ],
            "warnings": res.warnings,
        }

    # ------------------------------------------------------------------
    # Step 2: Run all analytical tools
    # ------------------------------------------------------------------

    def run_analysis(
        self,
        vendor: str,
        evaluation_period: str = "all",
        *,
        months: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Run the full analysis pipeline for a vendor.

        Parameters
        ----------
        vendor : str
            The vendor name to analyse.
        evaluation_period : str
            Human-readable description of the period (e.g. "2025-H1").
        months : list[str], optional
            Specific months to filter usage data.

        Returns
        -------
        dict with results from all tools.
        """
        self.state.vendor = vendor
        self.state.evaluation_period = evaluation_period
        output: dict[str, Any] = {}

        # Load data files
        usage_path = self.data_dir / "usage.csv"
        incidents_path = self.data_dir / "incidents.csv"
        quotations_path = self.data_dir / "quotations.xlsx"

        usage_result = load_usage(usage_path)
        incidents_result = load_incidents(incidents_path)
        quotations_result = load_quotations(quotations_path)

        for res, name in [
            (usage_result, "usage.csv"),
            (incidents_result, "incidents.csv"),
            (quotations_result, "quotations.xlsx"),
        ]:
            if not res.success:
                self.state.errors.append(f"Could not load {name}: {res.errors}")
            self.state.warnings.extend(res.warnings)

        # --- Utilisation ---
        if usage_result.success:
            util = calculate_utilisation_rate(
                usage_result.data, vendor=vendor, months=months
            )
            self.state.utilisation_result = util
            self.state.warnings.extend(util.warnings)
            output["utilisation"] = {
                "period_average_pct": str(util.period_average_pct),
                "vendor_summaries": {
                    k: {kk: str(vv) for kk, vv in v.items()}
                    for k, v in util.vendor_summaries.items()
                },
                "recommendation_notes": util.recommendation_notes,
                "warnings": util.warnings,
                "errors": util.errors,
            }

        # --- SLA ---
        if incidents_result.success:
            sla = evaluate_sla_performance(incidents_result.data, vendor=vendor)
            self.state.sla_result = sla
            self.state.warnings.extend(sla.warnings)
            output["sla"] = {
                "status": sla.status,
                "eligible_incidents": sla.eligible_incidents,
                "met_sla_count": sla.met_sla_count,
                "breached_count": sla.breached_count,
                "achievement_pct": str(sla.achievement_pct),
                "severity_breakdown": {
                    sev: {
                        "total": bd.total_incidents,
                        "met": bd.met_sla,
                        "breached": bd.breached,
                        "achievement_pct": str(bd.achievement_pct),
                        "breach_ids": bd.breach_incident_ids,
                    }
                    for sev, bd in sla.severity_breakdown.items()
                },
                "recommendation_notes": sla.recommendation_notes,
                "warnings": sla.warnings,
            }

        # --- Cost comparison ---
        if quotations_result.success:
            cost = compare_vendor_costs(quotations_result.data, vendor=vendor)
            self.state.cost_result = cost
            self.state.warnings.extend(cost.warnings)
            output["cost_comparison"] = cost.to_dict()

        # --- Deadline ---
        if self.state.contract_terms:
            ct = self.state.contract_terms
            if ct.contract_end.is_found() and ct.notice_period_days.is_found():
                deadline = calculate_notice_deadline(
                    vendor=vendor,
                    contract_end_date=ct.contract_end.value,
                    notice_period_days=int(ct.notice_period_days.value),
                    source_clause=ct.notice_period_days.evidence,
                )
                self.state.deadline_result = deadline
                self.state.warnings.extend(deadline.warnings)
                output["deadline"] = {
                    "contract_end": str(ct.contract_end.value),
                    "notice_period_days": ct.notice_period_days.value,
                    "notice_deadline": str(deadline.notice_deadline),
                    "days_until_deadline": deadline.days_until_deadline,
                    "alert_level": deadline.alert_level,
                    "alert_message": deadline.alert_message,
                    "calculation_note": deadline.calculation_note,
                }

        output["errors"] = self.state.errors
        output["warnings"] = list(set(self.state.warnings))  # deduplicate

        return output

    # ------------------------------------------------------------------
    # Step 3: Generate recommendation
    # ------------------------------------------------------------------

    def generate_recommendation(self) -> dict[str, Any]:
        """
        Produce an evidence-backed renewal recommendation.

        Returns
        -------
        dict with recommendation text, evidence, and required approvals.
        """
        vendor = self.state.vendor
        issues: list[str] = list(self.state.errors)
        warnings: list[str] = list(self.state.warnings)
        evidence: list[str] = []
        recommendation_options: list[str] = []

        # Check completeness
        can_recommend = True

        if not self.state.contract_terms:
            issues.append("No contract terms available — cannot assess renewal conditions.")
            can_recommend = False

        if not self.state.utilisation_result or self.state.utilisation_result.errors:
            issues.append("Utilisation data unavailable.")

        if not self.state.sla_result or self.state.sla_result.status == "NO_DATA":
            issues.append("SLA performance data unavailable.")

        if not self.state.cost_result or self.state.cost_result.errors:
            issues.append("Cost comparison data unavailable.")

        # Gather evidence signals
        util_signal = "NEUTRAL"
        sla_signal = "NEUTRAL"
        cost_signal = "NEUTRAL"

        if self.state.utilisation_result and not self.state.utilisation_result.errors:
            util = self.state.utilisation_result
            vendor_summary = util.vendor_summaries.get(
                vendor, util.vendor_summaries.get(vendor.lower(), {})
            )
            # Try case-insensitive match
            if not vendor_summary:
                for k, v in util.vendor_summaries.items():
                    if k.lower() == vendor.lower():
                        vendor_summary = v
                        break
            if vendor_summary:
                avg_pct = float(vendor_summary.get("average_utilisation_pct", 0))
                evidence.append(
                    f"Utilisation: {avg_pct:.1f}% average "
                    f"(threshold: {util.low_threshold_pct}%)"
                )
                if avg_pct < util.low_threshold_pct:
                    util_signal = "RENEGOTIATE"
                    recommendation_options.append("renegotiate")
                else:
                    util_signal = "RENEW"

        if self.state.sla_result and self.state.sla_result.status == "CALCULATED":
            sla = self.state.sla_result
            ach = float(sla.achievement_pct)
            evidence.append(
                f"SLA Achievement: {ach:.1f}% "
                f"({sla.met_sla_count}/{sla.eligible_incidents} incidents met SLA)"
            )
            if ach < 85.0:
                sla_signal = "REPLACE"
                recommendation_options.append("replace")
            elif ach < 95.0:
                sla_signal = "RENEGOTIATE"
                recommendation_options.append("renegotiate")
            else:
                sla_signal = "RENEW"

        if self.state.cost_result and not self.state.cost_result.errors:
            cost = self.state.cost_result
            if cost.recommendation_pending:
                cost_signal = "PENDING"
                issues.append(
                    "Replacement cost assessment is PENDING — migration cost not supplied."
                )
            else:
                cost_signal = "CALCULATED"
                evidence.append("Cost comparison available (see cost_comparison section).")

        # --- Deadline urgency ---
        if self.state.deadline_result:
            dl = self.state.deadline_result
            if dl.alert_level == AlertLevel.PASSED:
                can_recommend = False
                issues.append(
                    f"URGENT: Notice deadline has PASSED. Legal review is required before any recommendation can be acted on."
                )
            elif dl.alert_level == AlertLevel.URGENT:
                warnings.append(
                    f"Notice deadline is {dl.days_until_deadline} day(s) away — urgent action required."
                )

        # --- Build recommendation text ---
        if not can_recommend:
            rec_text = (
                "⚠️ INSUFFICIENT INFORMATION OR URGENT ISSUE: "
                "A definitive recommendation cannot be made at this time.\n\n"
                "Issues preventing recommendation:\n"
                + "\n".join(f"- {i}" for i in issues)
                + "\n\nRequired actions:\n"
                "- Resolve the issues listed above.\n"
                "- Obtain legal review if a deadline has passed.\n"
                "- Provide complete cost and contract data."
            )
        elif cost_signal == "PENDING":
            rec_text = (
                "⚠️ PENDING: Replacement cost data is incomplete. "
                "A full three-way comparison cannot be made.\n\n"
                "Current findings:\n"
                f"- Utilisation signal: {util_signal}\n"
                f"- SLA signal: {sla_signal}\n\n"
                "Pending: migration cost for replacement option.\n\n"
                "Recommended action: Request a migration cost estimate, then re-run this assessment."
            )
        else:
            # Determine dominant recommendation
            if "replace" in recommendation_options and cost_signal == "CALCULATED":
                top_rec = "CONSIDER REPLACEMENT"
                rationale = (
                    "Both SLA performance and cost analysis suggest the current vendor "
                    "may not be meeting requirements. Replacement options should be evaluated."
                )
            elif "renegotiate" in recommendation_options:
                top_rec = "CONSIDER RENEGOTIATION"
                rationale = (
                    "Utilisation and/or SLA findings suggest renegotiating licence quantities, "
                    "pricing, or service terms may deliver better value than straightforward renewal."
                )
            else:
                top_rec = "CONSIDER RENEWAL"
                rationale = (
                    "Current performance metrics are within acceptable ranges. "
                    "Renewal at current or renegotiated terms appears reasonable."
                )

            rec_text = (
                f"📋 ADVISORY RECOMMENDATION: {top_rec}\n\n"
                f"Rationale: {rationale}\n\n"
                f"Evidence:\n" + "\n".join(f"- {e}" for e in evidence) +
                "\n\n⚠️ REQUIRED: All contractual decisions require review and approval "
                "by your legal and procurement teams. This system cannot execute any contract actions."
            )

        self.state.recommendation = rec_text

        executive_summary = (
            f"Vendor Renewal Assessment: {vendor} | Period: {self.state.evaluation_period}\n"
            f"Contract: {self.state.contract_file or 'Not loaded'}\n"
            f"SLA Status: {getattr(self.state.sla_result, 'status', 'N/A')}\n"
            f"Missing Information: {', '.join(self.state.missing_information) or 'None'}\n"
            f"Open Warnings: {len(warnings)}"
        )
        self.state.executive_summary = executive_summary

        return {
            "recommendation": rec_text,
            "executive_summary": executive_summary,
            "evidence": evidence,
            "issues": issues,
            "warnings": warnings[:20],  # limit for readability
            "signals": {
                "utilisation": util_signal,
                "sla": sla_signal,
                "cost": cost_signal,
            },
            "human_approval_required": True,
            "disclaimer": (
                "This is an advisory report only. The agent cannot renew, terminate, "
                "sign, modify, or cancel any contract. Legal and procurement approval is required."
            ),
        }

    # ------------------------------------------------------------------
    # Step 4: Save assessment
    # ------------------------------------------------------------------

    def save_assessment(self, allow_overwrite: bool = False) -> dict[str, Any]:
        """Save the current assessment to the outputs directory."""
        if not self.state.vendor:
            return {"saved": False, "message": "No vendor set — run analysis first."}

        assessment = {
            "vendor": self.state.vendor,
            "evaluation_period": self.state.evaluation_period,
            "contract_file": self.state.contract_file,
            "executive_summary": self.state.executive_summary,
            "recommendation": self.state.recommendation,
            "warnings": self.state.warnings,
            "errors": self.state.errors,
            "missing_information": self.state.missing_information,
            "cost_comparison": (
                self.state.cost_result.to_dict()
                if self.state.cost_result else None
            ),
            "sla_summary": (
                f"Achievement: {self.state.sla_result.achievement_pct}%, "
                f"Eligible: {self.state.sla_result.eligible_incidents}, "
                f"Breached: {self.state.sla_result.breached_count}"
                if self.state.sla_result else "N/A"
            ),
            "utilisation_summary": (
                f"Period average: {self.state.utilisation_result.period_average_pct}%"
                if self.state.utilisation_result else "N/A"
            ),
            "assumptions": [
                "Sample data is fictional and for demonstration only.",
                "Low-utilisation threshold is 70% (configurable, not an industry standard).",
                "All dates are based on the contract text and today's date.",
            ],
            "human_review_notes": (
                "This assessment requires review by qualified legal and procurement personnel "
                "before any contractual action is taken."
            ),
        }

        return save_renewal_assessment(
            assessment,
            output_dir=self.output_dir,
            allow_overwrite=allow_overwrite,
        )

    # ------------------------------------------------------------------
    # Convenience: full pipeline
    # ------------------------------------------------------------------

    def run_full_assessment(
        self,
        vendor: str,
        contract_file: Optional[str | Path],
        evaluation_period: str = "all",
        months: Optional[list[str]] = None,
        save: bool = True,
    ) -> dict[str, Any]:
        """
        Run the complete assessment pipeline in one call.

        Parameters
        ----------
        vendor : str
        contract_file : str or Path or None
        evaluation_period : str
        months : list[str], optional
        save : bool
            Whether to save the assessment after completion.

        Returns
        -------
        dict with all results combined.
        """
        result: dict[str, Any] = {"vendor": vendor}

        # Contract
        if contract_file and Path(contract_file).exists():
            contract_out = self.load_contract(contract_file)
            result["contract"] = contract_out
        else:
            result["contract"] = {
                "success": False,
                "error": f"Contract file not found: {contract_file}",
            }
            self.state.missing_information.append("contract document")

        # Analysis
        analysis_out = self.run_analysis(vendor, evaluation_period, months=months)
        result.update(analysis_out)

        # Recommendation
        rec_out = self.generate_recommendation()
        result["recommendation_report"] = rec_out

        # Save
        if save:
            save_out = self.save_assessment()
            result["save_result"] = save_out

        return result
