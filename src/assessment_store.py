"""
assessment_store.py
-------------------
Saves and loads renewal assessments in a duplicate-safe way.

PURPOSE (English):
    Each assessment gets a unique ID and timestamp.
    Saving the same logical assessment twice is detected and blocked
    unless the user explicitly allows overwrite.
    Assessments are stored as JSON files in the outputs/ directory.

PURPOSE (Hindi):
    Har assessment ko unique ID aur timestamp milti hai.
    Ek hi assessment dobara save karne ki koshish detect hoti hai
    aur user ki permission ke bina block hoti hai.
    Assessments JSON files ke roop mein outputs/ folder mein save hoti hain.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import uuid

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("outputs")


def _generate_assessment_id(vendor: str, evaluation_period: str, timestamp: str) -> str:
    """Generate a deterministic-ish unique ID for an assessment."""
    base = f"{vendor}|{evaluation_period}|{timestamp}"
    short_hash = hashlib.sha256(base.encode()).hexdigest()[:8]
    return f"ASSESS-{vendor.upper()[:6]}-{short_hash}"


def save_renewal_assessment(
    assessment_data: dict[str, Any],
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    allow_overwrite: bool = False,
    generate_markdown: bool = True,
) -> dict[str, Any]:
    """
    Save a completed renewal assessment to disk as JSON (and optionally Markdown).

    Parameters
    ----------
    assessment_data : dict
        The assessment dictionary. Must contain at least:
        - 'vendor' (str)
        - 'evaluation_period' (str)
        - 'recommendation' (str or dict)
    output_dir : str or Path
        Directory to save outputs (default: outputs/).
    allow_overwrite : bool
        If True, an existing assessment with the same ID may be overwritten.
        Default False — prevents accidental data loss.
    generate_markdown : bool
        If True, also generate a Markdown summary report.

    Returns
    -------
    dict with keys:
        - 'saved': bool
        - 'assessment_id': str
        - 'json_path': str
        - 'markdown_path': str or None
        - 'message': str
        - 'duplicate_detected': bool

    Notes
    -----
    This function validates the assessment before saving.
    It does NOT overwrite previous assessments without explicit permission.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Validate required fields ---
    required = ("vendor", "evaluation_period")
    missing = [k for k in required if k not in assessment_data]
    if missing:
        return {
            "saved": False,
            "assessment_id": None,
            "json_path": None,
            "markdown_path": None,
            "message": f"Assessment is missing required fields: {missing}. Not saved.",
            "duplicate_detected": False,
        }

    vendor = str(assessment_data["vendor"])
    eval_period = str(assessment_data["evaluation_period"])

    # --- Assign ID and timestamp ---
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    assessment_id = _generate_assessment_id(vendor, eval_period, timestamp)

    # Allow caller to supply their own ID (e.g. for idempotent resaves)
    if "assessment_id" not in assessment_data:
        assessment_data["assessment_id"] = assessment_id
    else:
        assessment_id = str(assessment_data["assessment_id"])

    if "created_at" not in assessment_data:
        assessment_data["created_at"] = datetime.now(tz=timezone.utc).isoformat()

    # --- Check for existing file ---
    json_filename = f"{assessment_id}.json"
    json_path = out_dir / json_filename
    duplicate_detected = json_path.exists()

    if duplicate_detected and not allow_overwrite:
        return {
            "saved": False,
            "assessment_id": assessment_id,
            "json_path": str(json_path),
            "markdown_path": None,
            "message": (
                f"Assessment '{assessment_id}' already exists at '{json_path}'. "
                "Set allow_overwrite=True to replace it."
            ),
            "duplicate_detected": True,
        }

    # --- Save JSON ---
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(assessment_data, f, indent=2, default=str)
        logger.info("Assessment saved: %s", json_path)
    except OSError as exc:
        return {
            "saved": False,
            "assessment_id": assessment_id,
            "json_path": str(json_path),
            "markdown_path": None,
            "message": f"Failed to save JSON: {exc}",
            "duplicate_detected": duplicate_detected,
        }

    # --- Generate Markdown report ---
    md_path = None
    if generate_markdown:
        md_filename = f"{assessment_id}_report.md"
        md_path_obj = out_dir / md_filename
        md_content = _generate_markdown_report(assessment_data)
        try:
            md_path_obj.write_text(md_content, encoding="utf-8")
            md_path = str(md_path_obj)
            logger.info("Markdown report saved: %s", md_path)
        except OSError as exc:
            logger.warning("Could not save Markdown report: %s", exc)

    return {
        "saved": True,
        "assessment_id": assessment_id,
        "json_path": str(json_path),
        "markdown_path": md_path,
        "message": (
            f"Assessment '{assessment_id}' saved successfully."
            + (" (overwrote existing)" if duplicate_detected else "")
        ),
        "duplicate_detected": duplicate_detected,
    }


def _generate_markdown_report(data: dict[str, Any]) -> str:
    """Generate a readable Markdown report from assessment data."""
    vendor = data.get("vendor", "Unknown")
    period = data.get("evaluation_period", "Unknown")
    assess_id = data.get("assessment_id", "Unknown")
    created = data.get("created_at", "Unknown")
    recommendation = data.get("recommendation", "Not provided")

    lines = [
        f"# IT Vendor Renewal Assessment",
        f"",
        f"**Assessment ID:** {assess_id}",
        f"**Vendor:** {vendor}",
        f"**Evaluation Period:** {period}",
        f"**Created:** {created}",
        f"",
        f"---",
        f"",
        f"## Executive Summary",
        f"",
        f"{data.get('executive_summary', '_No summary provided._')}",
        f"",
        f"## Recommendation",
        f"",
        f"{recommendation}",
        f"",
        f"## Cost Comparison",
        f"",
    ]

    cost_data = data.get("cost_comparison", {})
    if cost_data:
        options = cost_data.get("options", {})
        if options:
            lines.append("| Option | Annual Cost | Migration Cost | First-Year Total | Savings vs Renew |")
            lines.append("|--------|-------------|----------------|-----------------|-----------------|")
            for opt, oc in options.items():
                ann = oc.get("annual_cost", "N/A")
                mig = oc.get("migration_cost", "N/A")
                fyt = oc.get("first_year_total", "N/A")
                sav = oc.get("savings_vs_renew", "N/A")
                lines.append(f"| {opt} | {ann} | {mig} | {fyt} | {sav} |")
        lines.append("")
        for w in cost_data.get("warnings", []):
            lines.append(f"> ⚠️ {w}")
    else:
        lines.append("_No cost comparison data._")

    lines += [
        "",
        "## SLA Performance",
        "",
        f"{data.get('sla_summary', '_No SLA data provided._')}",
        "",
        "## Licence Utilisation",
        "",
        f"{data.get('utilisation_summary', '_No utilisation data provided._')}",
        "",
        "## Contract & Deadline Warnings",
        "",
    ]

    warnings = data.get("warnings", [])
    if warnings:
        for w in warnings:
            lines.append(f"- ⚠️ {w}")
    else:
        lines.append("_No warnings._")

    lines += [
        "",
        "## Assumptions",
        "",
    ]
    assumptions = data.get("assumptions", [])
    if assumptions:
        for a in assumptions:
            lines.append(f"- {a}")
    else:
        lines.append("_No assumptions recorded._")

    lines += [
        "",
        "## Human Review Required",
        "",
        data.get("human_review_notes", "_No specific human review requirements recorded._"),
        "",
        "---",
        "",
        "> **DISCLAIMER:** This assessment is produced by an AI advisory system.",
        "> It is NOT legal advice. All contractual decisions require review and approval",
        "> by qualified legal and procurement personnel.",
        "> The system cannot renew, terminate, cancel, sign, or modify contracts.",
    ]

    return "\n".join(lines)


def load_assessment(assessment_id: str, output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Optional[dict]:
    """
    Load a previously saved assessment by ID.

    Parameters
    ----------
    assessment_id : str
    output_dir : str or Path

    Returns
    -------
    dict or None if not found.
    """
    path = Path(output_dir) / f"{assessment_id}.json"
    if not path.exists():
        logger.warning("Assessment not found: %s", path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_assessments(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> list[dict]:
    """List all saved assessment IDs and metadata from the output directory."""
    out_dir = Path(output_dir)
    if not out_dir.exists():
        return []
    results = []
    for json_file in sorted(out_dir.glob("ASSESS-*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            results.append({
                "assessment_id": data.get("assessment_id"),
                "vendor": data.get("vendor"),
                "evaluation_period": data.get("evaluation_period"),
                "created_at": data.get("created_at"),
                "file": str(json_file),
            })
        except Exception as exc:
            logger.warning("Could not read assessment file %s: %s", json_file, exc)
    return results
