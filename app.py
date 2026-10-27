"""
app.py
------
IT Vendor Renewal Decision Support Agent – Enterprise Dashboard
Polished, modern Streamlit UI for procurement, IT, and legal teams.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.agent import VendorRenewalAgent, check_forbidden_action
from src.contract_reader import read_contract
from src.contract_extractor import extract_contract_terms
from src.report_generator import generate_executive_markdown, generate_executive_html

# Page Config
st.set_page_config(
    page_title="IT Vendor Renewal Agent",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: #0F1117; }
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
  [data-testid="stSidebar"] {
      background: linear-gradient(180deg, #161B27 0%, #1A2035 100%);
      border-right: 1px solid #2A3349;
  }
  [data-testid="stSidebar"] label { color: #94A3B8 !important; font-size: 0.8rem; }
  .app-header {
      background: linear-gradient(135deg, #1E3A5F 0%, #1A2A4A 50%, #0F1F3D 100%);
      border: 1px solid #2A4A7F;
      border-radius: 14px;
      padding: 1.4rem 2rem;
      margin-bottom: 1.4rem;
      position: relative;
      overflow: hidden;
  }
  .app-header::before {
      content: '';
      position: absolute;
      top: -50%; right: -10%;
      width: 400px; height: 400px;
      background: radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%);
      pointer-events: none;
  }
  .app-header-title { font-size: 1.75rem; font-weight: 700; color: #F1F5F9; letter-spacing: -0.02em; margin: 0; }
  .app-header-sub   { font-size: 0.88rem; color: #94A3B8; margin: 0.25rem 0 0 0; }
  .app-header-badge {
      display: inline-flex; align-items: center; gap: 0.4rem;
      background: rgba(245,158,11,0.15); color: #FCD34D;
      border: 1px solid rgba(245,158,11,0.35);
      border-radius: 6px; padding: 0.3rem 0.8rem;
      font-size: 0.75rem; font-weight: 600; letter-spacing: 0.04em; margin-top: 0.9rem;
  }
  .kpi-card {
      background: linear-gradient(145deg, #1E2A3E, #1A2235);
      border: 1px solid #2A3A5A;
      border-radius: 12px; padding: 1.15rem 1.25rem;
      position: relative; overflow: hidden;
      transition: border-color 0.2s, transform 0.15s;
  }
  .kpi-card:hover { border-color: #3B82F6; transform: translateY(-2px); }
  .kpi-card::after {
      content: ''; position: absolute;
      top: 0; left: 0; right: 0; height: 3px;
      border-radius: 12px 12px 0 0;
  }
  .kpi-card.kpi-danger::after  { background: linear-gradient(90deg, #EF4444, #DC2626); }
  .kpi-card.kpi-warning::after { background: linear-gradient(90deg, #F59E0B, #D97706); }
  .kpi-card.kpi-success::after { background: linear-gradient(90deg, #10B981, #059669); }
  .kpi-card.kpi-info::after    { background: linear-gradient(90deg, #3B82F6, #2563EB); }
  .kpi-card.kpi-neutral::after { background: linear-gradient(90deg, #64748B, #475569); }
  .kpi-label { font-size: 0.68rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 0.5rem; }
  .kpi-value { font-size: 1.65rem; font-weight: 700; color: #F1F5F9; line-height: 1.1; margin: 0; }
  .kpi-sub   { font-size: 0.75rem; color: #64748B; margin-top: 0.35rem; }
  .kpi-badge { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.04em; }
  .badge-danger  { background: rgba(239,68,68,0.18);  color: #F87171; }
  .badge-warning { background: rgba(245,158,11,0.18); color: #FCD34D; }
  .badge-success { background: rgba(16,185,129,0.18); color: #34D399; }
  .badge-info    { background: rgba(59,130,246,0.18); color: #60A5FA; }
  .badge-neutral { background: rgba(100,116,139,0.2); color: #94A3B8; }
  .section-title { font-size: 1.05rem; font-weight: 600; color: #CBD5E1; border-left: 3px solid #3B82F6; padding-left: 0.65rem; margin: 1.2rem 0 0.75rem 0; }
  .callout { border-radius: 10px; padding: 0.9rem 1.1rem; font-size: 0.87rem; line-height: 1.55; margin-bottom: 0.75rem; border-left: 4px solid; }
  .callout-danger  { background: rgba(239,68,68,0.1);  border-color: #EF4444; color: #FCA5A5; }
  .callout-warning { background: rgba(245,158,11,0.1); border-color: #F59E0B; color: #FCD34D; }
  .callout-success { background: rgba(16,185,129,0.1); border-color: #10B981; color: #6EE7B7; }
  .callout-info    { background: rgba(59,130,246,0.1); border-color: #3B82F6; color: #93C5FD; }
  .checklist-item { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.6rem; border-radius: 6px; font-size: 0.82rem; margin-bottom: 0.3rem; color: #CBD5E1; }
  .checklist-item.missing { background: rgba(239,68,68,0.1); color: #FCA5A5; }
  .checklist-item.ok      { background: rgba(16,185,129,0.08); color: #6EE7B7; }
  .stTabs [data-baseweb="tab-list"] { background: #1A2235; border-radius: 10px; padding: 4px; gap: 2px; border: 1px solid #2A3349; }
  .stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 0.45rem 1rem; font-size: 0.82rem; font-weight: 500; color: #64748B; background: transparent; }
  .stTabs [aria-selected="true"] { background: #2563EB !important; color: #FFFFFF !important; }
  .stButton > button, .stDownloadButton > button { background: linear-gradient(135deg, #2563EB, #1D4ED8); color: #FFFFFF; border: none; border-radius: 8px; font-weight: 600; font-size: 0.83rem; padding: 0.5rem 1.2rem; transition: opacity 0.2s, transform 0.15s; }
  .stButton > button:hover, .stDownloadButton > button:hover { opacity: 0.88; transform: translateY(-1px); }
  hr { border-color: #2A3349; margin: 1.25rem 0; }
  .sidebar-section { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.1em; color: #475569; font-weight: 600; margin: 1.1rem 0 0.4rem 0; }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:1.2rem;">
      <span style="font-size:1.5rem;">⚖️</span>
      <div>
        <div style="font-size:0.95rem;font-weight:700;color:#E2E8F0;">Vendor Agent</div>
        <div style="font-size:0.7rem;color:#475569;">Assessment Setup</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">🏢 Vendor</div>', unsafe_allow_html=True)
    vendor_choice = st.selectbox("Select Vendor", ["VendorA", "VendorB", "Custom..."], label_visibility="collapsed", key="vendor_select")
    if vendor_choice == "Custom...":
        vendor_name = st.text_input("Vendor name", "VendorC")
    else:
        vendor_name = vendor_choice

    st.markdown('<div class="sidebar-section">📅 Evaluation Period</div>', unsafe_allow_html=True)
    eval_period = st.text_input("Period", "2025-H1", label_visibility="collapsed")

    st.markdown('<div class="sidebar-section">📄 Contract Document</div>', unsafe_allow_html=True)
    contracts_dir = BASE_DIR / "data" / "contracts"
    contract_options = ["None"]
    if contracts_dir.exists():
        contract_options += [f.name for f in sorted(contracts_dir.iterdir()) if f.is_file()]

    default_idx = 0
    if vendor_name == "VendorA" and len(contract_options) > 1:
        default_idx = 1
    elif vendor_name == "VendorB" and len(contract_options) > 2:
        default_idx = 2

    selected_contract_name = st.selectbox("Contract", contract_options, index=default_idx, label_visibility="collapsed", key="contract_select")
    contract_path = None
    if selected_contract_name != "None":
        contract_path = contracts_dir / selected_contract_name

    st.markdown('<div class="sidebar-section">📤 Or Upload Contract</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload (.txt, .pdf, .docx)", type=["txt", "pdf", "docx"], label_visibility="collapsed")
    if uploaded_file is not None:
        temp_dir = BASE_DIR / "data" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        contract_path = temp_dir / uploaded_file.name
        with open(contract_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"✅ {uploaded_file.name}")

    st.markdown('<div class="sidebar-section">⚙️ Analysis Options</div>', unsafe_allow_html=True)
    low_util_threshold = st.slider("Low Utilisation Threshold (%)", 50, 90, 70, 5, help="Licences used below this % are flagged as over-purchased.")
    save_assessment = st.checkbox("Save Assessment to Disk", value=True)

    st.markdown("---")
    st.markdown('<div style="font-size:0.7rem;color:#334155;text-align:center;line-height:1.6;">Advisory only · No contractual authority<br>All actions require legal approval</div>', unsafe_allow_html=True)

# Header
st.markdown(f"""
<div class="app-header">
  <p class="app-header-title">⚖️ IT Vendor Renewal Decision Support Agent</p>
  <p class="app-header-sub">Evidence-based advisory assessment for enterprise contracts, licence utilisation, SLAs, and migration costs</p>
  <div class="app-header-badge">⚠️ ADVISORY SYSTEM ONLY — Cannot renew, terminate, sign, or modify contracts. Requires legal &amp; procurement approval.</div>
</div>
""", unsafe_allow_html=True)

# Run Agent
agent = VendorRenewalAgent(data_dir=BASE_DIR / "data", output_dir=BASE_DIR / "outputs")
with st.spinner("🔍 Analysing contract, licence utilisation, incidents, and renewal options…"):
    result = agent.run_full_assessment(
        vendor=vendor_name,
        contract_file=str(contract_path) if contract_path else None,
        evaluation_period=eval_period,
        save=save_assessment,
    )

# Helper
def _fmt_num(val, decimals=2, prefix="", suffix=""):
    try:
        return f"{prefix}{float(val):,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return "—"

def _pct(val):
    return _fmt_num(val, 1, suffix="%")

# Extract results
deadline_info = result.get("deadline") or {}
util_info     = result.get("utilisation") or {}
sla_info      = result.get("sla") or {}
cost_info     = result.get("cost_comparison") or {}
options_data  = cost_info.get("options") or {}
rec_report    = result.get("recommendation_report") or {}
contract_res  = result.get("contract") or {}

deadline_alert = deadline_info.get("alert_level", "UNKNOWN")
deadline_date  = deadline_info.get("deadline_date", "N/A")
days_left      = deadline_info.get("days_until_deadline")
avg_util       = util_info.get("period_average_pct", None)
sla_pct        = sla_info.get("achievement_pct", None)
renew_cost     = options_data.get("renew", {}).get("annual_cost", None)

# KPI Cards
def _kpi_html(label, value_html, sub, card_cls, badge_html=""):
    return f"""<div class="kpi-card {card_cls}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value_html}</div>
      {f'<div style="margin-top:0.35rem">{badge_html}</div>' if badge_html else ""}
      <div class="kpi-sub">{sub}</div>
    </div>"""

c1, c2, c3, c4 = st.columns(4)

# KPI 1 – Deadline
if deadline_alert in ("PASSED", "URGENT"):
    dl_cls = "kpi-danger"; dl_badge = f'<span class="kpi-badge badge-danger">🔴 {deadline_alert}</span>'
elif deadline_alert == "WARNING":
    dl_cls = "kpi-warning"; dl_badge = f'<span class="kpi-badge badge-warning">🟡 {deadline_alert}</span>'
elif deadline_alert == "OK":
    dl_cls = "kpi-success"; dl_badge = f'<span class="kpi-badge badge-success">🟢 OK</span>'
else:
    dl_cls = "kpi-neutral"; dl_badge = f'<span class="kpi-badge badge-neutral">— UNKNOWN</span>'
days_txt = f"{days_left}d remaining" if days_left is not None else "Days unknown"
with c1:
    st.markdown(_kpi_html("Notice Deadline", deadline_date, days_txt, dl_cls, dl_badge), unsafe_allow_html=True)

# KPI 2 – Utilisation
if avg_util is not None:
    avg_f = float(avg_util)
    util_low = avg_f < low_util_threshold
    util_cls = "kpi-warning" if util_low else "kpi-success"
    util_badge = ('<span class="kpi-badge badge-warning">⚠️ Over-purchased</span>' if util_low
                  else '<span class="kpi-badge badge-success">✅ Normal usage</span>')
    util_val = _pct(avg_f); util_sub = f"Threshold: {low_util_threshold}%"
else:
    util_cls = "kpi-neutral"; util_badge = '<span class="kpi-badge badge-neutral">— No data</span>'
    util_val = "—"; util_sub = "Usage data unavailable"
with c2:
    st.markdown(_kpi_html("Avg Licence Utilisation", util_val, util_sub, util_cls, util_badge), unsafe_allow_html=True)

# KPI 3 – SLA
if sla_pct is not None:
    sla_f = float(sla_pct)
    sla_cls = "kpi-danger" if sla_f < 80 else ("kpi-warning" if sla_f < 95 else "kpi-success")
    sla_badge_cls = "badge-danger" if sla_f < 80 else ("badge-warning" if sla_f < 95 else "badge-success")
    sla_badge = f'<span class="kpi-badge {sla_badge_cls}">{"❌ Below target" if sla_f < 95 else "✅ On target"}</span>'
    met = sla_info.get("met_sla_count", "?"); elig = sla_info.get("eligible_incidents", "?")
    sla_sub = f"{met} / {elig} incidents met target"
else:
    sla_cls = "kpi-neutral"; sla_badge = '<span class="kpi-badge badge-neutral">— No data</span>'
    sla_f = None; sla_sub = "Incident data unavailable"
with c3:
    st.markdown(_kpi_html("SLA Achievement", _pct(sla_f) if sla_f is not None else "—", sla_sub, sla_cls, sla_badge), unsafe_allow_html=True)

# KPI 4 – Cost
if renew_cost is not None:
    cost_cls = "kpi-info"; cost_badge = '<span class="kpi-badge badge-info">💷 Annual cost</span>'
    cost_val = _fmt_num(renew_cost, 0, "£"); cost_sub = f"Baseline: {cost_info.get('baseline', 'renew')}"
else:
    cost_cls = "kpi-neutral"; cost_badge = '<span class="kpi-badge badge-neutral">— No quotation</span>'
    cost_val = "—"; cost_sub = "Quotation data unavailable"
with c4:
    st.markdown(_kpi_html("Proposed Renewal Cost", cost_val, cost_sub, cost_cls, cost_badge), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Missing Data Checklist
data_checks = [
    ("Contract document loaded",      contract_res.get("success", False)),
    ("Licence usage data available",  avg_util is not None),
    ("Incident / SLA data available", sla_pct is not None),
    ("Quotation options available",   bool(options_data)),
    ("Deadline info available",       deadline_alert not in ("UNKNOWN",)),
]
missing_count = sum(1 for _, ok in data_checks if not ok)
if missing_count > 0:
    with st.expander(f"⚠️ {missing_count} data source(s) unavailable — expand to see checklist", expanded=False):
        cols_chk = st.columns(2)
        for i, (label, ok) in enumerate(data_checks):
            icon = "✅" if ok else "❌"; cls = "ok" if ok else "missing"
            cols_chk[i % 2].markdown(f'<div class="checklist-item {cls}">{icon} {label}</div>', unsafe_allow_html=True)

# Tabs
tab_rec, tab_cost, tab_sla, tab_util, tab_contract, tab_search, tab_guardrails = st.tabs([
    "📋 Overview", "💰 Cost", "⏱️ SLA", "📊 Utilisation",
    "📄 Contract Terms", "🔍 Clause Search", "🛡️ Safeguards",
])

# ── Overview ──
with tab_rec:
    recommendation_text = rec_report.get("recommendation", "")
    evidence_list = rec_report.get("evidence", [])
    issues_list   = rec_report.get("issues", [])
    warnings_list = result.get("warnings", [])

    if recommendation_text:
        rec_lower = recommendation_text.lower()
        if any(w in rec_lower for w in ["renew", "proceed"]):
            rec_cls = "callout-success"
        elif any(w in rec_lower for w in ["caution", "risk", "concern", "flag"]):
            rec_cls = "callout-warning"
        elif any(w in rec_lower for w in ["migrate", "renegotiate", "reject"]):
            rec_cls = "callout-danger"
        else:
            rec_cls = "callout-info"
        st.markdown(f'<div class="callout {rec_cls}">📌 <strong>Advisory Recommendation:</strong><br>{recommendation_text}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="callout callout-info">ℹ️ No recommendation generated. Ensure data files are present and a contract is selected.</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    col_ev, col_issues = st.columns([3, 2])
    with col_ev:
        st.markdown('<div class="section-title">🔍 Evidence &amp; Findings</div>', unsafe_allow_html=True)
        if evidence_list:
            for ev in evidence_list:
                st.markdown(f"- {ev}")
        else:
            st.markdown('<div class="callout callout-info">No evidence items generated.</div>', unsafe_allow_html=True)
    with col_issues:
        st.markdown('<div class="section-title">⚠️ Open Issues &amp; Warnings</div>', unsafe_allow_html=True)
        if issues_list:
            for iss in issues_list:
                st.markdown(f'<div class="callout callout-danger">❌ {iss}</div>', unsafe_allow_html=True)
        if warnings_list:
            for w in warnings_list[:5]:
                st.markdown(f'<div class="callout callout-warning">⚠️ {w}</div>', unsafe_allow_html=True)
        if not issues_list and not warnings_list:
            st.markdown('<div class="callout callout-success">✅ No open issues detected.</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">📥 Export Executive Reports</div>', unsafe_allow_html=True)
    exec_md = generate_executive_markdown(result)
    exec_html = generate_executive_html(result)
    ex1, ex2, _ = st.columns([1, 1, 2])
    with ex1:
        st.download_button("📥 Download Markdown Report", data=exec_md, file_name=f"{vendor_name}_Renewal_Report.md", mime="text/markdown")
    with ex2:
        st.download_button("🌐 Download HTML Report", data=exec_html, file_name=f"{vendor_name}_Renewal_Report.html", mime="text/html")

# ── Cost ──
with tab_cost:
    st.markdown('<div class="section-title">💰 Three-Way Renewal Cost Matrix</div>', unsafe_allow_html=True)
    st.caption("All figures in GBP calculated with deterministic Decimal arithmetic.")
    if options_data:
        table_rows = []
        for opt_name, opt_c in options_data.items():
            annual = opt_c.get("annual_cost"); migration = opt_c.get("migration_cost")
            fy_total = opt_c.get("first_year_total"); savings = opt_c.get("savings_vs_renew")
            complete = opt_c.get("is_complete", False)
            table_rows.append({
                "Option": opt_name.capitalize(),
                "Annual Cost (£)": _fmt_num(annual, 2) if annual else "N/A",
                "Migration Cost (£)": _fmt_num(migration, 2) if migration else "0.00",
                "First-Year Total (£)": _fmt_num(fy_total, 2) if fy_total else "N/A",
                "Savings vs Renew (£)": _fmt_num(savings, 2) if savings else "0.00",
                "Data Completeness": "✅ Complete" if complete else "⚠️ Pending migration cost",
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        chart_rows = []
        for opt_name, opt_c in options_data.items():
            ann = opt_c.get("annual_cost"); mig = opt_c.get("migration_cost")
            if ann:
                chart_rows.append({"Option": opt_name.capitalize(), "Type": "Annual Cost", "£": float(ann)})
            if mig and float(mig) > 0:
                chart_rows.append({"Option": opt_name.capitalize(), "Type": "Migration Cost", "£": float(mig)})
        if chart_rows:
            st.markdown('<div class="section-title">📊 Cost Breakdown Chart</div>', unsafe_allow_html=True)
            chart_df = pd.DataFrame(chart_rows).pivot(index="Option", columns="Type", values="£").fillna(0)
            st.bar_chart(chart_df)

        best_opt = None; best_saving = 0
        for opt_name, opt_c in options_data.items():
            sv = opt_c.get("savings_vs_renew")
            if sv:
                try:
                    sv_f = float(sv)
                    if sv_f > best_saving:
                        best_saving = sv_f; best_opt = opt_name
                except (TypeError, ValueError):
                    pass
        if best_opt and best_saving > 0:
            st.markdown(f'<div class="callout callout-success">💡 <strong>{best_opt.capitalize()}</strong> offers the highest potential saving of <strong>£{best_saving:,.2f}</strong> versus renewal.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="callout callout-warning">⚠️ No quotation options found for this vendor in quotations.xlsx.<br>Add rows for this vendor to see cost comparison.</div>', unsafe_allow_html=True)

# ── SLA ──
with tab_sla:
    st.markdown('<div class="section-title">⏱️ Service Level Agreement Performance</div>', unsafe_allow_html=True)
    st.caption("Target compliance based on historical incident response records.")
    sev_bd = sla_info.get("severity_breakdown") or {}
    if sev_bd:
        bd_rows = []
        for sev, data in sev_bd.items():
            ach = data.get("achievement_pct", "0")
            bd_rows.append({
                "Severity": sev.capitalize(),
                "Total Incidents": data.get("total", 0),
                "Met Target": data.get("met", 0),
                "Breached": data.get("breached", 0),
                "Achievement %": f"{ach}%",
                "Breach IDs": ", ".join(data.get("breach_ids", [])) or "—",
            })
        st.dataframe(pd.DataFrame(bd_rows), use_container_width=True, hide_index=True)
        if sla_pct is not None:
            sla_f = float(sla_pct)
            cls = "callout-success" if sla_f >= 95 else ("callout-warning" if sla_f >= 80 else "callout-danger")
            icon = "✅" if sla_f >= 95 else "⚠️"
            st.markdown(f'<div class="callout {cls}">{icon} Overall SLA achievement: <strong>{sla_pct}%</strong> across {sla_info.get("eligible_incidents", "?")} eligible incidents.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="callout callout-info">ℹ️ No incident records available for this vendor in incidents.csv.</div>', unsafe_allow_html=True)

# ── Utilisation ──
with tab_util:
    st.markdown('<div class="section-title">📊 Licence Usage &amp; Over-Purchasing Analysis</div>', unsafe_allow_html=True)
    st.caption(f"Monthly active seats versus total purchased licences (flagged if usage < {low_util_threshold}%).")
    usage_file = BASE_DIR / "data" / "usage.csv"
    if usage_file.exists():
        df_usage = pd.read_csv(usage_file)
        v_usage  = df_usage[df_usage["vendor"] == vendor_name]
        if not v_usage.empty:
            if "licences_active" in v_usage.columns and "licences_purchased" in v_usage.columns:
                v_usage = v_usage.copy()
                v_usage["utilisation_%"] = ((v_usage["licences_active"] / v_usage["licences_purchased"]) * 100).round(1)
            st.dataframe(v_usage.reset_index(drop=True), use_container_width=True, hide_index=True)
            if "licences_purchased" in v_usage.columns and "licences_active" in v_usage.columns:
                st.markdown('<div class="section-title">📈 Monthly Licence Usage Trend</div>', unsafe_allow_html=True)
                st.line_chart(v_usage[["month", "licences_purchased", "licences_active"]].set_index("month"))
            if avg_util is not None and float(avg_util) < low_util_threshold:
                st.markdown(f'<div class="callout callout-warning">⚠️ Average utilisation <strong>{avg_util}%</strong> is below the {low_util_threshold}% threshold. Consider reducing licence count at renewal to save costs.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="callout callout-info">ℹ️ No usage data found for <strong>{vendor_name}</strong> in usage.csv.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="callout callout-warning">⚠️ usage.csv not found in the data/ directory.</div>', unsafe_allow_html=True)
    for note in util_info.get("recommendation_notes", []):
        st.markdown(f'<div class="callout callout-info">💡 {note}</div>', unsafe_allow_html=True)

# ── Contract Terms ──
with tab_contract:
    st.markdown('<div class="section-title">📄 Extracted Contractual Terms</div>', unsafe_allow_html=True)
    if contract_res.get("success"):
        terms_dict = contract_res.get("terms") or {}
        term_fields = ["vendor_name", "contract_start", "contract_end", "renewal_type", "notice_period_days", "notice_deadline", "annual_cost"]
        term_rows = []
        for fld in term_fields:
            f_obj = terms_dict.get(fld) or {}
            val = f_obj.get("value", "NOT FOUND"); conf = f_obj.get("confidence", "NOT_FOUND")
            evid = f_obj.get("evidence", "")
            evid_short = (evid[:130] + "…") if len(evid) > 130 else evid
            term_rows.append({"Field": fld.replace("_", " ").title(), "Extracted Value": val, "Confidence": conf, "Supporting Evidence": evid_short or "—"})
        st.dataframe(pd.DataFrame(term_rows), use_container_width=True, hide_index=True)
        low_conf = [r for r in term_rows if r["Confidence"] in ("LOW", "NOT_FOUND", "MEDIUM")]
        if low_conf:
            fields_str = ", ".join(r["Field"] for r in low_conf)
            st.markdown(f'<div class="callout callout-warning">⚠️ Low or missing confidence for: <strong>{fields_str}</strong>. Manual review recommended.</div>', unsafe_allow_html=True)
    elif contract_path:
        st.markdown(f'<div class="callout callout-danger">❌ Contract could not be read: {contract_res.get("error", "Unknown error")}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="callout callout-info">ℹ️ <strong>No contract selected.</strong><br>Choose a contract from the sidebar dropdown or upload a file (.txt, .pdf, .docx) to extract terms.</div>', unsafe_allow_html=True)

# ── Clause Search ──
with tab_search:
    st.markdown('<div class="section-title">🔍 Local Contract Clause Retriever (BM25)</div>', unsafe_allow_html=True)
    st.caption(f"Search for specific clauses within the loaded contract for **{vendor_name}** — strict vendor isolation enforced.")
    c_search, c_btn = st.columns([4, 1])
    with c_search:
        search_q = st.text_input("Search query", "notice period", placeholder="e.g. service credits, termination fee…", label_visibility="collapsed")
    with c_btn:
        do_search = st.button("Search", use_container_width=True)
    st.caption("Try: `notice period` · `service credits` · `termination fee` · `data processing` · `liability cap`")
    if do_search:
        if not contract_path:
            st.markdown('<div class="callout callout-warning">⚠️ No contract loaded. Select or upload a contract first.</div>', unsafe_allow_html=True)
        else:
            with st.spinner("Searching indexed contract clauses…"):
                search_res = agent.search_contract(search_q, top_k=5)
            matches = search_res.get("matches", [])
            if matches:
                st.markdown(f'<div class="callout callout-success">✅ Found <strong>{len(matches)}</strong> clause(s) across {search_res.get("total_chunks_searched", "?")} indexed sections.</div>', unsafe_allow_html=True)
                for m in matches:
                    header_txt = f"{m['section']} Relevance: {m['relevance']}, Score: {m['score']}"
                    with st.expander(header_txt, expanded=(m == matches[0])):
                        if m.get("clause"):
                            st.caption(f"Clause: {m['clause']}")
                        st.code(m["content"], language="")
            else:
                st.markdown('<div class="callout callout-info">ℹ️ No matching clauses found for this query.</div>', unsafe_allow_html=True)
                for w in search_res.get("warnings", []):
                    st.markdown(f'<div class="callout callout-warning">⚠️ {w}</div>', unsafe_allow_html=True)

# ── Safeguards ──
with tab_guardrails:
    st.markdown('<div class="section-title">🛡️ Advisory Boundaries &amp; Safeguard Testing</div>', unsafe_allow_html=True)
    st.markdown('<div class="callout callout-info">This agent operates under strict advisory boundaries.<br>It <strong>cannot</strong> renew, terminate, sign, approve, or modify any contract.<br>Use this panel to verify that safeguards correctly block forbidden requests.</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🚫 Forbidden Action Categories</div>', unsafe_allow_html=True)
    forbidden_cols = st.columns(3)
    categories = [
        ("🔴 Contractual", ["Terminate contract", "Cancel agreement", "Execute contract"]),
        ("🟠 Renewal",     ["Auto-renew", "Approve renewal", "Sign contract"]),
        ("🟡 Notices",     ["Send termination notice", "Renew automatically"]),
    ]
    for idx, (cat_name, examples) in enumerate(categories):
        with forbidden_cols[idx]:
            st.markdown(f"**{cat_name}**")
            for ex in examples:
                st.markdown(f"- `{ex}`")
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">🧪 Test a Query</div>', unsafe_allow_html=True)
    test_q_col, test_btn_col = st.columns([4, 1])
    with test_q_col:
        test_query = st.text_input("Test query", "Please terminate contract VendorA immediately.", label_visibility="collapsed")
    with test_btn_col:
        run_test = st.button("Test", use_container_width=True)
    if run_test:
        blocked_msg = check_forbidden_action(test_query)
        if blocked_msg:
            st.markdown(f'<div class="callout callout-danger">🛑 <strong>ACTION BLOCKED BY SAFEGUARD:</strong><br><pre style="white-space:pre-wrap;color:#FCA5A5;background:transparent;border:none;padding:0;margin:0.5rem 0 0 0">{blocked_msg}</pre></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="callout callout-success">✅ <strong>Query Allowed:</strong> This is an analytical / informational request within the agent\'s scope.</div>', unsafe_allow_html=True)
