"""
report_generator.py
-------------------
Produces executive-ready decision reports and procurement sign-off packages
in both Markdown and self-contained HTML formats.

PURPOSE (English):
    While assessment_store.py saves raw machine data and basic markdown,
    this module formats formal executive summaries, side-by-side option matrices,
    risk registries, and formal multi-stakeholder sign-off sheets for CIOs,
    Legal Counsel, and Procurement Committees.

PURPOSE (Hindi):
    Yeh module executive-level reports aur sign-off documents tayyar karta hai.
    Isme teeno options (Renew, Renegotiate, Replace) ki comparison matrix,
    risk factors, aur CIO, Legal, tatha Procurement leads ke signature blocks hote hain.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def generate_executive_markdown(assessment: dict[str, Any]) -> str:
    """Generate a formal executive renewal report in Markdown format."""
    vendor = assessment.get("vendor", "Unknown Vendor")
    period = assessment.get("evaluation_period", "Unspecified")
    created = assessment.get("created_at", datetime.now(timezone.utc).isoformat())
    cost_info = assessment.get("cost_comparison", {})
    sla_info = assessment.get("sla", {})
    util_info = assessment.get("utilisation", {})
    rec_report = assessment.get("recommendation_report", {})
    deadline = assessment.get("deadline", {})
    contract_data = assessment.get("contract", {})

    lines: list[str] = [
        f"# IT VENDOR RENEWAL DECISION PACKAGE",
        f"**Confidential -- For Internal Procurement Committee Review Only**\n",
        f"- **Vendor:** {vendor}",
        f"- **Evaluation Period:** {period}",
        f"- **Assessment Date:** {created[:10]}",
        f"- **Notice Deadline:** {deadline.get('deadline_date', 'N/A')} [{deadline.get('alert_level', 'UNKNOWN')}]",
        f"\n---\n",
        f"## 1. Executive Summary & Advisory Recommendation",
        f"",
        rec_report.get("recommendation", "No recommendation available."),
        f"",
        f"### Key Rationale & Findings:",
    ]

    for ev in rec_report.get("evidence", []):
        lines.append(f"- {ev}")

    lines.extend([
        f"",
        f"## 2. Options Comparison Matrix",
        f"",
        f"| Decision Factor | Option 1: Renew | Option 2: Renegotiate | Option 3: Replace |",
        f"|---|---|---|---|",
    ])

    opts = cost_info.get("options", {})
    renew_opt = opts.get("renew", {})
    reneg_opt = opts.get("renegotiate", {})
    replace_opt = opts.get("replace", {})

    c_renew = f"GBP {float(renew_opt.get('annual_cost', 0)):,.2f}" if renew_opt.get("annual_cost") else "N/A"
    c_reneg = f"GBP {float(reneg_opt.get('annual_cost', 0)):,.2f}" if reneg_opt.get("annual_cost") else "N/A"
    c_replace = f"GBP {float(replace_opt.get('annual_cost', 0)):,.2f}" if replace_opt.get("annual_cost") else "N/A"

    mig_cost = f"GBP {float(replace_opt.get('migration_cost', 0)):,.2f}" if replace_opt.get("migration_cost") else "N/A (Pending)"
    tot_replace = f"GBP {float(replace_opt.get('first_year_total', 0)):,.2f}" if replace_opt.get("first_year_total") else "Pending"

    lines.extend([
        f"| **Annual Licence Cost** | {c_renew} | {c_reneg} | {c_replace} |",
        f"| **One-Time Migration Cost** | GBP 0.00 | GBP 0.00 | {mig_cost} |",
        f"| **First Year Total Cost** | {c_renew} | {c_reneg} | {tot_replace} |",
        f"| **Savings vs Proposed** | Baseline | GBP {float(reneg_opt.get('savings_vs_renew', 0)):,.2f} | GBP {float(replace_opt.get('savings_vs_renew', 0)):,.2f} |",
        f"| **Implementation Risk** | Low (Status quo) | Low (Contractual only) | High (Data & workflow migration) |",
        f"| **SLA Performance** | Historical {sla_info.get('achievement_pct', 'N/A')}% | Requires revised terms | New vendor benchmark |",
        f"",
        f"## 3. Contractual Standing & Notice Deadline",
        f"",
        f"- **Contract Start / End:** {contract_data.get('terms', {}).get('contract_start', {}).get('value', 'N/A')} to {contract_data.get('terms', {}).get('contract_end', {}).get('value', 'N/A')}",
        f"- **Notice Period:** {contract_data.get('terms', {}).get('notice_period_days', {}).get('value', 'N/A')} days",
        f"- **Deadline Status:** {deadline.get('alert_message', 'No deadline alert available')}",
        f"- **Calculation Note:** {deadline.get('calculation_note', '')}",
        f"",
        f"## 4. Risk & Compliance Registry",
        f"",
    ])

    warnings = assessment.get("warnings", [])
    if warnings:
        for idx, w in enumerate(warnings, 1):
            lines.append(f"{idx}. [Warning] {w}")
    else:
        lines.append("- No high-severity risks identified.")

    lines.extend([
        f"",
        f"## 5. Formal Governance & Sign-Off Authorization",
        f"",
        f"All contractual actions require formal sign-off. This advisory assessment cannot execute transactions.",
        f"",
        f"```text",
        f"1. IT Vendor Manager",
        f"   Name: ______________________   Signature: ___________________   Date: _________",
        f"",
        f"2. Procurement Category Lead",
        f"   Name: ______________________   Signature: ___________________   Date: _________",
        f"",
        f"3. Legal Counsel",
        f"   Name: ______________________   Signature: ___________________   Date: _________",
        f"",
        f"4. Chief Information Officer (CIO) / VP IT",
        f"   Name: ______________________   Signature: ___________________   Date: _________",
        f"```",
        f"",
        f"> **LEGAL DISCLAIMER:** This report was generated by an AI decision support tool for informational purposes only. It does not constitute binding legal or financial counsel.",
    ])

    return "\n".join(lines)


def generate_executive_html(assessment: dict[str, Any]) -> str:
    """Generate a print-ready, styled HTML executive report."""
    md_content = generate_executive_markdown(assessment)
    vendor = assessment.get("vendor", "Vendor")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>IT Vendor Renewal Assessment -- {vendor}</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        line-height: 1.6;
        color: #1e293b;
        max-width: 900px;
        margin: 40px auto;
        padding: 0 20px;
    }}
    h1 {{ color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }}
    h2 {{ color: #334155; margin-top: 30px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 10px 14px; text-align: left; }}
    th {{ background-color: #f1f5f9; font-weight: 600; }}
    .alert-box {{ background: #fef3c7; border: 1px solid #fcd34d; padding: 14px; border-radius: 6px; margin: 15px 0; }}
    .signoff-box {{ background: #f8fafc; border: 1px dashed #94a3b8; padding: 18px; border-radius: 6px; font-family: monospace; }}
    .disclaimer {{ font-size: 0.85rem; color: #64748b; margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 15px; }}
</style>
</head>
<body>
<pre style="white-space: pre-wrap; font-family: inherit;">{md_content}</pre>
</body>
</html>
"""
    return html
