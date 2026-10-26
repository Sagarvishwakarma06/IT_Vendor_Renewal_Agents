"""
data_loader.py
--------------
Loads and validates CSV / XLSX input files for the agent.

PURPOSE (English):
    This module reads usage.csv, incidents.csv, and quotations.xlsx.
    It validates column names, data types, and catches common errors
    (missing files, wrong columns, negative values, zero licences, etc.)
    so the rest of the system always receives clean, predictable data.

PURPOSE (Hindi):
    Yeh module usage, incidents, aur quotations files ko padhta hai.
    Sab columns aur values ko check karta hai - jaise negative numbers,
    missing columns, ya galat formats. Baaki system ko saaf data milta hai.
"""

import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expected schemas
# ---------------------------------------------------------------------------

USAGE_COLUMNS = {"vendor", "month", "licences_purchased", "licences_active"}
INCIDENTS_COLUMNS = {"vendor", "incident_id", "severity", "response_hours", "sla_hours"}
QUOTATIONS_COLUMNS = {"vendor", "option", "annual_cost", "migration_cost"}

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_OPTIONS = {"renew", "renegotiate", "replace"}

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

class LoadResult:
    """
    Wraps a loaded DataFrame together with validation messages.

    Attributes
    ----------
    success  : True if the file was loaded and passed validation.
    data     : Pandas DataFrame (empty DataFrame on failure).
    warnings : Non-fatal issues found during validation.
    errors   : Fatal issues that prevent reliable use of the data.
    source   : Path of the source file.
    """

    def __init__(
        self,
        success: bool,
        data: pd.DataFrame,
        source: Path,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        self.success = success
        self.data = data
        self.source = source
        self.warnings = warnings or []
        self.errors = errors or []

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAILED"
        return (
            f"LoadResult({status}, rows={len(self.data)}, "
            f"warnings={len(self.warnings)}, errors={len(self.errors)}, "
            f"file={self.source.name!r})"
        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _check_columns(df: pd.DataFrame, required: set[str], source: Path) -> list[str]:
    """Return error messages for any missing required columns."""
    missing = required - set(df.columns.str.lower())
    if missing:
        return [
            f"Missing required columns in '{source.name}': {sorted(missing)}. "
            f"Found columns: {list(df.columns)}"
        ]
    return []


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase and strip all column names."""
    df.columns = [c.strip().lower() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# usage.csv loader
# ---------------------------------------------------------------------------

def load_usage(file_path: str | Path) -> LoadResult:
    """
    Load and validate the licence usage CSV file.

    Expected columns: vendor, month, licences_purchased, licences_active.

    Validation checks:
    - File exists
    - Required columns present
    - Numeric columns are numeric (non-negative)
    - Licences active <= licences purchased (warn if violated)
    - Zero purchased licences (flagged per row)

    Parameters
    ----------
    file_path : str or Path
        Path to usage.csv.

    Returns
    -------
    LoadResult
    """
    path = Path(file_path)
    warnings: list[str] = []
    errors: list[str] = []
    empty_df = pd.DataFrame()

    if not path.exists():
        return LoadResult(False, empty_df, path, errors=[f"File not found: '{path}'"])

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return LoadResult(False, empty_df, path, errors=[f"Cannot read CSV: {exc}"])

    df = _normalise_columns(df)
    col_errors = _check_columns(df, USAGE_COLUMNS, path)
    if col_errors:
        return LoadResult(False, empty_df, path, errors=col_errors)

    # Coerce numeric columns
    for col in ("licences_purchased", "licences_active"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
        bad = df[col].isna()
        if bad.any():
            warnings.append(
                f"Column '{col}' has {bad.sum()} non-numeric value(s) — rows will be excluded."
            )

    df = df.dropna(subset=["licences_purchased", "licences_active"])

    # Negative values
    for col in ("licences_purchased", "licences_active"):
        neg = df[col] < 0
        if neg.any():
            errors.append(f"Column '{col}' contains {neg.sum()} negative value(s). Invalid data.")

    if errors:
        return LoadResult(False, empty_df, path, warnings=warnings, errors=errors)

    # Zero purchased licences (not a fatal error, but flagged for division safety)
    zero_purchased = df["licences_purchased"] == 0
    if zero_purchased.any():
        warnings.append(
            f"{zero_purchased.sum()} row(s) have licences_purchased = 0. "
            "Utilisation cannot be calculated for these rows and they will be skipped."
        )

    # Active > Purchased inconsistency
    inconsistent = df["licences_active"] > df["licences_purchased"]
    if inconsistent.any():
        warnings.append(
            f"{inconsistent.sum()} row(s) have licences_active > licences_purchased. "
            "Please verify the data — this may indicate a data entry error."
        )

    # Strip whitespace from string columns
    df["vendor"] = df["vendor"].astype(str).str.strip()
    df["month"] = df["month"].astype(str).str.strip()

    logger.info("Loaded usage data: %d rows from '%s'", len(df), path.name)
    return LoadResult(True, df, path, warnings=warnings)


# ---------------------------------------------------------------------------
# incidents.csv loader
# ---------------------------------------------------------------------------

def load_incidents(file_path: str | Path) -> LoadResult:
    """
    Load and validate the incident records CSV file.

    Expected columns: vendor, incident_id, severity, response_hours, sla_hours.

    Validation checks:
    - File exists
    - Required columns present
    - Numeric response_hours and sla_hours (non-negative)
    - Known severity values
    - Duplicate incident IDs (warned)
    - Negative values (error)

    Parameters
    ----------
    file_path : str or Path
        Path to incidents.csv.

    Returns
    -------
    LoadResult
    """
    path = Path(file_path)
    warnings: list[str] = []
    errors: list[str] = []
    empty_df = pd.DataFrame()

    if not path.exists():
        return LoadResult(False, empty_df, path, errors=[f"File not found: '{path}'"])

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return LoadResult(False, empty_df, path, errors=[f"Cannot read CSV: {exc}"])

    df = _normalise_columns(df)
    col_errors = _check_columns(df, INCIDENTS_COLUMNS, path)
    if col_errors:
        return LoadResult(False, empty_df, path, errors=col_errors)

    # String normalisation
    for col in ("vendor", "incident_id", "severity"):
        df[col] = df[col].astype(str).str.strip()

    df["severity"] = df["severity"].str.lower()

    # Severity validation
    unknown_sev = ~df["severity"].isin(VALID_SEVERITIES)
    if unknown_sev.any():
        bad_vals = df.loc[unknown_sev, "severity"].unique().tolist()
        warnings.append(
            f"Unknown severity value(s) {bad_vals}. "
            f"Expected one of {sorted(VALID_SEVERITIES)}. "
            "Affected rows will be included but flagged."
        )

    # Numeric coercion
    for col in ("response_hours", "sla_hours"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
        bad = df[col].isna()
        if bad.any():
            warnings.append(
                f"Column '{col}' has {bad.sum()} non-numeric value(s) — rows will be excluded."
            )

    df = df.dropna(subset=["response_hours", "sla_hours"])

    # Negative values
    for col in ("response_hours", "sla_hours"):
        neg = df[col] < 0
        if neg.any():
            errors.append(f"Column '{col}' contains {neg.sum()} negative value(s). Invalid data.")

    if errors:
        return LoadResult(False, empty_df, path, warnings=warnings, errors=errors)

    # Duplicate incident IDs
    dupe_ids = df["incident_id"].duplicated(keep=False)
    if dupe_ids.any():
        dupes = df.loc[dupe_ids, "incident_id"].unique().tolist()
        warnings.append(
            f"Duplicate incident_id value(s) found: {dupes}. "
            "Results may double-count these incidents."
        )

    logger.info("Loaded incident data: %d rows from '%s'", len(df), path.name)
    return LoadResult(True, df, path, warnings=warnings)


# ---------------------------------------------------------------------------
# quotations.xlsx loader
# ---------------------------------------------------------------------------

def load_quotations(file_path: str | Path) -> LoadResult:
    """
    Load and validate the vendor quotations Excel file.

    Expected columns: vendor, option, annual_cost, migration_cost.

    Validation checks:
    - File exists
    - Required columns present
    - annual_cost and migration_cost are non-negative numbers
    - option values match expected set
    - Missing annual_cost flagged (prevents complete recommendation)

    Parameters
    ----------
    file_path : str or Path
        Path to quotations.xlsx.

    Returns
    -------
    LoadResult
    """
    path = Path(file_path)
    warnings: list[str] = []
    errors: list[str] = []
    empty_df = pd.DataFrame()

    if not path.exists():
        return LoadResult(False, empty_df, path, errors=[f"File not found: '{path}'"])

    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as exc:
        return LoadResult(False, empty_df, path, errors=[f"Cannot read Excel file: {exc}"])

    df = _normalise_columns(df)
    col_errors = _check_columns(df, QUOTATIONS_COLUMNS, path)
    if col_errors:
        return LoadResult(False, empty_df, path, errors=col_errors)

    # String normalisation
    df["vendor"] = df["vendor"].astype(str).str.strip()
    df["option"] = df["option"].astype(str).str.strip().str.lower()

    # Numeric coercion
    for col in ("annual_cost", "migration_cost"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Missing annual_cost is flagged — prevents full recommendation
    missing_cost = df["annual_cost"].isna()
    if missing_cost.any():
        affected = df.loc[missing_cost, ["vendor", "option"]].to_dict("records")
        warnings.append(
            f"Missing annual_cost for: {affected}. "
            "Cost comparison cannot be completed for these rows."
        )

    # Missing migration_cost is acceptable (may be zero)
    missing_migration = df["migration_cost"].isna()
    if missing_migration.any():
        affected = df.loc[missing_migration, ["vendor", "option"]].to_dict("records")
        warnings.append(
            f"Missing migration_cost for: {affected}. "
            "If migration is required, this cost must be supplied before recommending replacement."
        )
        df.loc[missing_migration, "migration_cost"] = None  # keep as NaN, not 0

    # Negative values
    for col in ("annual_cost", "migration_cost"):
        neg = df[col].notna() & (df[col] < 0)
        if neg.any():
            errors.append(f"Column '{col}' contains {neg.sum()} negative value(s). Invalid data.")

    if errors:
        return LoadResult(False, empty_df, path, warnings=warnings, errors=errors)

    # Unknown option values
    unknown_opts = ~df["option"].isin(VALID_OPTIONS)
    if unknown_opts.any():
        bad_vals = df.loc[unknown_opts, "option"].unique().tolist()
        warnings.append(
            f"Unknown option value(s) {bad_vals}. Expected: {sorted(VALID_OPTIONS)}."
        )

    logger.info("Loaded quotation data: %d rows from '%s'", len(df), path.name)
    return LoadResult(True, df, path, warnings=warnings)
