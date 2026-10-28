"""
generate_academic_report_pdf.py
--------------------------------
Compiles the comprehensive Academic Project Report from HTML to vector PDF
using Microsoft Edge headless print-to-pdf.
"""

import os
import subprocess
from pathlib import Path

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = BASE_DIR / "outputs"
HTML_FILE = OUTPUT_DIR / "IT_Vendor_Renewal_Decision_Support_Agent_Academic_Report.html"
PDF_FILE = BASE_DIR / "IT_Vendor_Renewal_Decision_Support_Agent_Academic_Report.pdf"

if not HTML_FILE.exists():
    raise FileNotFoundError(f"HTML file not found at: {HTML_FILE}")

print(f"[OK] Found Academic Report HTML at: {HTML_FILE} ({HTML_FILE.stat().st_size} bytes)")

edge_paths = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

edge_bin = None
for p in edge_paths:
    if os.path.exists(p):
        edge_bin = p
        break

if edge_bin:
    input_uri = "file:///" + str(HTML_FILE).replace("\\", "/")
    cmd = [
        edge_bin,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={PDF_FILE}",
        input_uri,
    ]
    print(f"[PDF] Compiling PDF using: {edge_bin} ...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if PDF_FILE.exists():
        size_kb = PDF_FILE.stat().st_size / 1024
        print(f"[SUCCESS] Academic Report PDF successfully created at:\n   {PDF_FILE}\n   Size: {size_kb:.1f} KB")
    else:
        print(f"[WARN] PDF creation attempted but file not found. Stderr: {res.stderr}")
else:
    print(f"[WARN] msedge.exe not found on system paths. HTML is available at: {HTML_FILE}")
