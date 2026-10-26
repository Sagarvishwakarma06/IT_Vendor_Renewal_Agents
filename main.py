"""
main.py
-------
Command-line entry point for the IT Vendor Renewal Decision Support Agent.

Usage:
    python main.py --vendor VendorA --contract data/contracts/VendorA_Contract.txt
    python main.py --vendor VendorA --contract data/contracts/VendorA_Contract.txt --months 2025-01 2025-02 2025-03

Run with --help for all options.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles to prevent charmap encoding errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Make src importable when running from project root
sys.path.insert(0, str(Path(__file__).parent))

from src.agent import VendorRenewalAgent


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="IT Vendor Renewal Decision Support Agent (Advisory Only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "DISCLAIMER: This tool is an advisory system only.\n"
            "It cannot renew, terminate, sign, or modify contracts.\n"
            "All decisions require human legal and procurement approval.\n\n"
            "Example:\n"
            "  python main.py --vendor VendorA "
            "--contract data/contracts/VendorA_Contract.txt"
        ),
    )
    parser.add_argument("--vendor", required=True, help="Vendor name to assess (e.g. VendorA)")
    parser.add_argument(
        "--contract",
        help="Path to the contract file (.txt, .pdf, or .docx)",
        default=None,
    )
    parser.add_argument(
        "--months",
        nargs="+",
        help="Specific months to evaluate (e.g. 2025-01 2025-02). Default: all months.",
        default=None,
    )
    parser.add_argument(
        "--period",
        default="all",
        help="Evaluation period description (e.g. '2025-H1'). Default: all.",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing usage.csv, incidents.csv, quotations.xlsx. Default: data/",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory to save assessment JSON and Markdown. Default: outputs/",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save the assessment to disk.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print full result as JSON instead of formatted text.",
    )
    parser.add_argument(
        "--search",
        help="Search for specific clauses in the contract (e.g. 'service credits', 'notice period').",
        default=None,
    )
    parser.add_argument(
        "--export-html",
        action="store_true",
        help="Export executive HTML decision report to output directory.",
    )
    return parser


def print_section(title: str, content: str, width: int = 70) -> None:
    print(f"\n{'='*width}")
    print(f"  {title}")
    print(f"{'='*width}")
    print(content)


def format_result(result: dict) -> str:
    """Format the assessment result for human-readable terminal output."""
    lines = []

    # Contract
    contract = result.get("contract", {})
    if contract.get("success"):
        terms = contract.get("terms", {})
        lines.append("CONTRACT TERMS EXTRACTED")
        for field in ["vendor_name", "contract_start", "contract_end", "renewal_type",
                      "notice_period_days", "notice_deadline", "annual_cost"]:
            fdata = terms.get(field, {})
            val = fdata.get("value", "NOT FOUND")
            conf = fdata.get("confidence", "")
            lines.append(f"  {field:25s}: {val} [{conf}]")
        missing = terms.get("missing_fields", [])
        if missing:
            lines.append(f"  Missing fields: {', '.join(missing)}")
    else:
        lines.append(f"CONTRACT: Not loaded — {contract.get('error', 'unknown error')}")

    # Deadline
    deadline = result.get("deadline")
    if deadline:
        lines.append(f"\nDEADLINE ALERT: [{deadline.get('alert_level')}] {deadline.get('alert_message')}")
        lines.append(f"  {deadline.get('calculation_note')}")

    # Utilisation
    util = result.get("utilisation", {})
    if util and not util.get("errors"):
        lines.append(f"\nUTILISATION: Period average: {util.get('period_average_pct')}%")
        for v, s in util.get("vendor_summaries", {}).items():
            lines.append(f"  {v}: avg={s.get('average_utilisation_pct')}%  low={s.get('is_low_average')}")
        for note in util.get("recommendation_notes", []):
            lines.append(f"  -> {note}")

    # SLA
    sla = result.get("sla", {})
    if sla:
        lines.append(f"\nSLA PERFORMANCE: Status={sla.get('status')}, "
                     f"Achievement={sla.get('achievement_pct')}% "
                     f"({sla.get('met_sla_count')}/{sla.get('eligible_incidents')} incidents met SLA)")
        for sev, bd in sla.get("severity_breakdown", {}).items():
            lines.append(
                f"  {sev:10s}: {bd['met']}/{bd['total']} met, "
                f"{bd['achievement_pct']}%, "
                f"breaches: {bd.get('breach_ids', [])}"
            )
        for note in sla.get("recommendation_notes", []):
            lines.append(f"  -> {note}")

    # Cost
    cost = result.get("cost_comparison", {})
    if cost:
        lines.append(f"\nCOST COMPARISON (baseline: {cost.get('baseline')})")
        opts = cost.get("options", {})
        lines.append(f"  {'Option':15s} {'Annual Cost':>14} {'Migration':>12} {'1st Yr Total':>14} {'Saving':>12}")
        lines.append(f"  {'-'*70}")
        for opt, oc in opts.items():
            ann  = oc.get("annual_cost") or "N/A"
            mig  = oc.get("migration_cost") or "0"
            fyt  = oc.get("first_year_total") or "N/A"
            sav  = oc.get("savings_vs_renew") or "0"
            pend = " ⚠️ PENDING" if not oc.get("is_complete") else ""
            lines.append(f"  {opt:15s} {str(ann):>14} {str(mig):>12} {str(fyt):>14} {str(sav):>12}{pend}")
        for w in cost.get("warnings", []):
            lines.append(f"  ⚠️ {w}")

    # Recommendation
    rec_report = result.get("recommendation_report", {})
    if rec_report:
        lines.append(f"\n{'='*70}")
        lines.append(rec_report.get("recommendation", "No recommendation generated."))
        lines.append(f"\n{'='*70}")
        lines.append(f"DISCLAIMER: {rec_report.get('disclaimer', '')}")

    # Warnings
    all_warnings = result.get("warnings", [])
    if all_warnings:
        lines.append(f"\n⚠️  WARNINGS ({len(all_warnings)}):")
        for w in all_warnings[:10]:
            lines.append(f"  - {w}")

    # Save result
    save = result.get("save_result", {})
    if save:
        if save.get("saved"):
            lines.append(f"\n✅ Assessment saved: {save.get('json_path')}")
            if save.get("markdown_path"):
                lines.append(f"   Markdown report: {save.get('markdown_path')}")
        else:
            lines.append(f"\n⚠️ Assessment not saved: {save.get('message')}")

    return "\n".join(lines)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)

    # Safety check on vendor name input
    if len(args.vendor) > 100 or not args.vendor.replace(" ", "").replace("-", "").isalnum():
        print("ERROR: Vendor name contains unexpected characters. Use alphanumeric names only.")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  IT Vendor Renewal Decision Support Agent")
    print(f"  Advisory System — Read Only — Human Approval Required")
    print(f"{'='*70}")
    print(f"  Vendor:          {args.vendor}")
    print(f"  Contract:        {args.contract or '(not supplied)'}")
    print(f"  Period:          {args.period}")
    print(f"  Months filter:   {args.months or 'all'}")
    print(f"  Data directory:  {args.data_dir}")
    print(f"  Output:          {'(not saving)' if args.no_save else args.output_dir}")
    print(f"{'='*70}\n")

    agent = VendorRenewalAgent(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
    )

    result = agent.run_full_assessment(
        vendor=args.vendor,
        contract_file=args.contract,
        evaluation_period=args.period,
        months=args.months,
        save=not args.no_save,
    )

    if args.json_output:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(format_result(result))

    if args.contract and args.search:
        search_res = agent.search_contract(args.search)
        print(f"\n{'='*70}")
        print(f"  CONTRACT CLAUSE SEARCH: '{args.search}'")
        print(f"{'='*70}")
        matches = search_res.get("matches", [])
        if matches:
            for m in matches:
                print(f"  [{m['relevance']}] {m['section']}")
                print(f"  Snippet: {m['snippet']}\n")
        else:
            print("  No matching clauses found.")

    if args.export_html:
        from src.report_generator import generate_executive_html
        html_content = generate_executive_html(result)
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / f"{args.vendor}_Executive_Report.html"
        html_path.write_text(html_content, encoding="utf-8")
        print(f"\n✅ Executive HTML report exported: {html_path}")


if __name__ == "__main__":
    main()
