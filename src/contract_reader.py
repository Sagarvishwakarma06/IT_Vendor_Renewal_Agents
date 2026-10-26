"""
contract_reader.py
------------------
Reads contract documents from TXT, PDF, and DOCX formats.

PURPOSE (English):
    This module opens a contract file and returns its raw text.
    It supports plain text, PDF (via pdfplumber), and DOCX files.
    It detects scanned/image-only PDFs and warns the user rather than
    silently returning empty text.

PURPOSE (Hindi):
    Yeh module contract file ko kholta hai aur uska text return karta hai.
    Yeh TXT, PDF, aur DOCX formats support karta hai.
    Agar PDF sirf image hai (scan ki hui), to yeh user ko batata hai
    ki OCR ki zarurat hai - silently khaali result nahi deta.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data container
# ---------------------------------------------------------------------------

class ContractReadResult:
    """
    Holds the outcome of reading one contract document.

    Attributes
    ----------
    success      : True if text was extracted, False otherwise.
    text         : The extracted text (empty string when unavailable).
    source_file  : Absolute path to the source document.
    pages        : Number of pages (PDF only; 0 for TXT/DOCX).
    warnings     : List of human-readable warnings (e.g. OCR required).
    error        : Error message when success is False.
    """

    def __init__(
        self,
        success: bool,
        text: str,
        source_file: Path,
        pages: int = 0,
        warnings: Optional[list[str]] = None,
        error: str = "",
    ) -> None:
        self.success = success
        self.text = text
        self.source_file = source_file
        self.pages = pages
        self.warnings = warnings or []
        self.error = error

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAILED"
        chars = len(self.text)
        return (
            f"ContractReadResult({status}, file={self.source_file.name!r}, "
            f"chars={chars}, pages={self.pages}, warnings={len(self.warnings)})"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_txt(path: Path) -> ContractReadResult:
    """Read a plain-text contract file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return ContractReadResult(
                success=False,
                text="",
                source_file=path,
                warnings=["File is empty or contains only whitespace."],
                error="Empty file.",
            )
        return ContractReadResult(success=True, text=text, source_file=path)
    except OSError as exc:
        msg = f"Cannot read file: {exc}"
        logger.error(msg)
        return ContractReadResult(success=False, text="", source_file=path, error=msg)


def _read_pdf(path: Path) -> ContractReadResult:
    """
    Read a PDF contract using pdfplumber.

    Detects image-only (scanned) PDFs by checking whether any page
    returned zero characters despite having content.
    """
    try:
        import pdfplumber  # imported here so TXT/DOCX paths work without it
    except ImportError:
        msg = "pdfplumber is not installed. Run: pip install pdfplumber"
        logger.error(msg)
        return ContractReadResult(success=False, text="", source_file=path, error=msg)

    warnings: list[str] = []
    pages_text: list[str] = []
    total_pages = 0
    image_only_pages: list[int] = []

    try:
        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                pages_text.append(page_text)
                # Heuristic: page has images but no text → likely scanned
                if not page_text.strip() and page.images:
                    image_only_pages.append(i)
    except Exception as exc:
        msg = f"Failed to open PDF '{path.name}': {exc}"
        logger.error(msg)
        return ContractReadResult(success=False, text="", source_file=path, error=msg)

    combined = "\n".join(pages_text)

    if image_only_pages:
        warnings.append(
            f"Pages {image_only_pages} appear to be image-only (scanned). "
            "OCR is required to extract text from these pages. "
            "Consider using pytesseract or a cloud OCR service."
        )

    if not combined.strip():
        # Entire PDF is empty text - likely fully scanned
        warnings.append(
            "No text could be extracted from this PDF. "
            "The document may be entirely image-based and require OCR."
        )
        return ContractReadResult(
            success=False,
            text="",
            source_file=path,
            pages=total_pages,
            warnings=warnings,
            error="No extractable text found in PDF.",
        )

    return ContractReadResult(
        success=True,
        text=combined,
        source_file=path,
        pages=total_pages,
        warnings=warnings,
    )


def _read_docx(path: Path) -> ContractReadResult:
    """Read a DOCX contract using python-docx."""
    try:
        from docx import Document  # type: ignore
    except ImportError:
        msg = "python-docx is not installed. Run: pip install python-docx"
        logger.error(msg)
        return ContractReadResult(success=False, text="", source_file=path, error=msg)

    try:
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs]
        text = "\n".join(paragraphs)
        if not text.strip():
            return ContractReadResult(
                success=False,
                text="",
                source_file=path,
                warnings=["DOCX file contains no readable paragraph text."],
                error="Empty DOCX.",
            )
        return ContractReadResult(success=True, text=text, source_file=path)
    except Exception as exc:
        msg = f"Failed to read DOCX '{path.name}': {exc}"
        logger.error(msg)
        return ContractReadResult(success=False, text="", source_file=path, error=msg)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def read_contract(file_path: str | Path) -> ContractReadResult:
    """
    Read a contract document and return its text content.

    Supports TXT, PDF, and DOCX formats.  Handles missing files,
    empty files, unsupported formats, and scanned PDFs gracefully.

    Parameters
    ----------
    file_path : str or Path
        Path to the contract document.

    Returns
    -------
    ContractReadResult
        Contains success flag, extracted text, warnings, and error details.

    Example
    -------
    >>> result = read_contract("data/contracts/VendorA_Contract.txt")
    >>> if result.success:
    ...     print(result.text[:200])
    """
    path = Path(file_path)

    # --- Guard: file must exist ---
    if not path.exists():
        msg = f"Contract file not found: '{path}'"
        logger.warning(msg)
        return ContractReadResult(success=False, text="", source_file=path, error=msg)

    # --- Guard: must be a file, not a directory ---
    if not path.is_file():
        msg = f"Path is not a file: '{path}'"
        logger.warning(msg)
        return ContractReadResult(success=False, text="", source_file=path, error=msg)

    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        msg = (
            f"Unsupported file format '{ext}' for '{path.name}'. "
            f"Supported formats: {sorted(SUPPORTED_EXTENSIONS)}"
        )
        logger.warning(msg)
        return ContractReadResult(success=False, text="", source_file=path, error=msg)

    logger.info("Reading contract: %s", path)

    if ext == ".txt":
        return _read_txt(path)
    elif ext == ".pdf":
        return _read_pdf(path)
    elif ext == ".docx":
        return _read_docx(path)

    # Should never reach here given the guard above
    return ContractReadResult(
        success=False, text="", source_file=path, error="Unexpected format error."
    )


# ---------------------------------------------------------------------------
# Quick self-test (run as script)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    contract_dir = Path("data") / "contracts"
    files = list(contract_dir.glob("*"))

    if not files:
        print("No contract files found in data/contracts/")
        sys.exit(1)

    for f in sorted(files):
        print(f"\n{'='*60}")
        result = read_contract(f)
        print(result)
        if result.success:
            # Print first 300 characters as a preview
            preview = result.text[:300].replace("\n", " ")
            print(f"Preview: {preview}...")
        if result.warnings:
            for w in result.warnings:
                print(f"WARNING: {w}")
        if result.error:
            print(f"ERROR: {result.error}")
