"""
app.py
------
Interactive Streamlit Web Application for the IT Vendor Renewal Decision Support Agent.
Provides an executive dashboard for procurement managers, CIOs, and vendor managers.
"""

import os
import sys
from pathlib import Path
from decimal import Decimal
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

# -----------------------------------------------------------------------------
# Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="IT Vendor Renewal Decision Support Agent",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Custom Styling
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .advisory-badge {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 0.75rem 1.2rem;
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid #FCD34D;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
    }
    .badge-urgent {
        background: #FEE2E2;
        color: #991B1B;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-ok {
        background: #DCFCE7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
st.markdown('<div class="main-title">IT Vendor Renewal Decision Support Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Evidence-based advisory assessment for enterprise contracts, utilisation, SLAs, and migration costs</div>', unsafe_allow_html=True)

st.markdown("""
<div class="advisory-badge">
    ⚠️ <strong>ADVISORY SYSTEM ONLY:</strong> This system provides non-binding recommendations. 
    It cannot renew, terminate, sign, or modify contracts. All actions require legal and procurement approval.
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Sidebar Configuration
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Evaluation Parameters")

vendor_choice = st.sidebar.selectbox(
    "Select Vendor",
    ["VendorA", "VendorB", "Custom..."]
)

if vendor_choice == "Custom...":
    vendor_name = st.sidebar.text_input("Enter Vendor Name", "VendorC")
else:
    vendor_name = vendor_choice

eval_period = st.sidebar.text_input("Evaluation Period", "2025-H1")

# Contract selection
contracts_dir = BASE_DIR / "data" / "contracts"
contract_options = ["None"]
if contracts_dir.exists():
    contract_options += [f.name for f in contracts_dir.iterdir() if f.is_file()]

selected_contract_name = st.sidebar.selectbox(
    "Contract Document",
    contract_options,
    index=1 if len(contract_options) > 1 and vendor_name == "VendorA" else (2 if len(contract_options) > 2 and vendor_name == "VendorB" else 0)
)

contract_path = None
if selected_contract_name != "None":
    contract_path = contracts_dir / selected_contract_name

uploaded_file = st.sidebar.file_uploader("Or Upload Contract (.txt, .pdf, .docx)", type=["txt", "pdf", "docx"])
if uploaded_file is not None:
    temp_dir = BASE_DIR / "data" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    contract_path = temp_dir / uploaded_file.name
    with open(contract_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.sidebar.success(f"Uploaded: {uploaded_file.name}")

st.sidebar.markdown("---")
low_util_threshold = st.sidebar.slider("Low Utilisation Threshold (%)", 50, 90, 70)
save_assessment = st.sidebar.checkbox("Save Assessment to Disk", value=True)

# -----------------------------------------------------------------------------
# Agent Execution
# -----------------------------------------------------------------------------
agent = VendorRenewalAgent(data_dir=BASE_DIR / "data", output_dir=BASE_DIR / "outputs")

# Run assessment
with st.spinner("Analyzing contract, licence utilisation, incident records, and quotation options..."):
    result = agent.run_full_assessment(
        vendor=vendor_name,
        contract_file=str(contract_path) if contract_path else None,
        evaluation_period=eval_period,
        save=save_assessment,
    )

# -----------------------------------------------------------------------------
# Key Metric KPI Tiles
# -----------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

deadline_info = result.get("deadline") or {}
deadline_alert = deadline_info.get("alert_level", "UNKNOWN")
deadline_date = deadline_info.get("deadline_date", "N/A")

util_info = result.get("utilisation") or {}
avg_util = util_info.get("period_average_pct", "0.0")

sla_info = result.get("sla") or {}
sla_pct = sla_info.get("achievement_pct", "0.0")

cost_info = result.get("cost_comparison") or {}
options_data = cost_info.get("options") or {}
renew_cost = options_data.get("renew", {}).get("annual_cost", "N/A")

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.caption("NOTICE DEADLINE")
    if deadline_alert in ["PASSED", "URGENT"]:
        st.markdown(f'<span class="badge-urgent">{deadline_alert}: {deadline_date}</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="badge-ok">{deadline_alert}: {deadline_date}</span>', unsafe_allow_html=True)
    st.write(f"Days remaining: {deadline_info.get('days_until_deadline', 'N/A')}")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.caption("AVERAGE UTILISATION")
    st.markdown(f"<h3>{avg_util}%</h3>", unsafe_allow_html=True)
    is_low = float(avg_util) < low_util_threshold if avg_util != "0.0" else False
    st.write("Over-purchased" if is_low else "Normal usage")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.caption("SLA ACHIEVEMENT")
    st.markdown(f"<h3>{sla_pct}%</h3>", unsafe_allow_html=True)
    st.write(f"{sla_info.get('met_sla_count', 0)} / {sla_info.get('eligible_incidents', 0)} met target")
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.caption("PROPOSED RENEWAL COST")
    st.markdown(f"<h3>GBP {renew_cost}</h3>", unsafe_allow_html=True)
    st.write(f"Baseline: {cost_info.get('baseline', 'renew')}")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Detailed Tabs
# -----------------------------------------------------------------------------
tab_rec, tab_cost, tab_sla, tab_util, tab_contract, tab_search, tab_guardrails = st.tabs([
    "📋 Advisory Recommendation",
    "💰 Cost Comparison",
    "⏱️ SLA Performance",
    "📊 Licence Utilisation",
    "📄 Contract Terms",
    "🔍 Clause Search (RAG)",
    "🛡️ Safeguards & Actions",
])

# TAB 1: RECOMMENDATION
with tab_rec:
    st.subheader("Advisory Decision Summary")
    rec_report = result.get("recommendation_report") or {}
    st.info(rec_report.get("recommendation", "No recommendation generated."))
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 🔍 Evidence & Findings")
        for ev in rec_report.get("evidence", []):
            st.markdown(f"- {ev}")
        if not rec_report.get("evidence"):
            st.write("No evidence items generated.")
            
    with col_b:
        st.markdown("#### ⚠️ Open Issues & Warnings")
        for iss in rec_report.get("issues", []):
            st.error(iss)
        for w in result.get("warnings", [])[:6]:
            st.warning(w)

    st.markdown("---")
    st.markdown("#### 📥 Executive Reports Export")
    exec_md = generate_executive_markdown(result)
    exec_html = generate_executive_html(result)

    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        st.download_button(
            label="📥 Download Executive Markdown Report",
            data=exec_md,
            file_name=f"{vendor_name}_Executive_Renewal_Report.md",
            mime="text/markdown",
        )
    with exp_col2:
        st.download_button(
            label="🌐 Download Print-Ready HTML Report",
            data=exec_html,
            file_name=f"{vendor_name}_Executive_Renewal_Report.html",
            mime="text/html",
        )

# TAB 2: COST COMPARISON
with tab_cost:
    st.subheader("Three-Way Renewal Cost Matrix")
    st.write("All figures in GBP calculated with deterministic Decimal arithmetic.")
    
    if options_data:
        table_rows = []
        for opt_name, opt_c in options_data.items():
            table_rows.append({
                "Option": opt_name.capitalize(),
                "Annual Cost (GBP)": f"{float(opt_c.get('annual_cost', 0)):,.2f}" if opt_c.get('annual_cost') else "N/A",
                "Migration Cost (GBP)": f"{float(opt_c.get('migration_cost', 0)):,.2f}" if opt_c.get('migration_cost') else "0.00",
                "First Year Total (GBP)": f"{float(opt_c.get('first_year_total', 0)):,.2f}" if opt_c.get('first_year_total') else "N/A",
                "Estimated Savings vs Renew (GBP)": f"{float(opt_c.get('savings_vs_renew', 0)):,.2f}" if opt_c.get('savings_vs_renew') else "0.00",
                "Data Completeness": "✅ Complete" if opt_c.get("is_complete") else "⚠️ Pending Migration Cost",
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

        # Bar chart comparison
        chart_data = []
        for opt_name, opt_c in options_data.items():
            if opt_c.get("first_year_total"):
                chart_data.append({
                    "Option": opt_name.capitalize(),
                    "Cost Type": "Annual Cost",
                    "Amount": float(opt_c.get("annual_cost", 0)),
                })
                if float(opt_c.get("migration_cost", 0)) > 0:
                    chart_data.append({
                        "Option": opt_name.capitalize(),
                        "Cost Type": "Migration Cost",
                        "Amount": float(opt_c.get("migration_cost", 0)),
                    })
        if chart_data:
            chart_df = pd.DataFrame(chart_data)
            st.bar_chart(chart_df, x="Option", y="Amount")
    else:
        st.warning("No quotation options found for this vendor in quotations.xlsx.")

# TAB 3: SLA PERFORMANCE
with tab_sla:
    st.subheader("Service Level Agreement (SLA) Analysis")
    st.write("Target compliance based on historical incident response records.")
    
    sev_bd = sla_info.get("severity_breakdown") or {}
    if sev_bd:
        bd_rows = []
        for sev, data in sev_bd.items():
            bd_rows.append({
                "Severity": sev.capitalize(),
                "Total Incidents": data.get("total", 0),
                "Met SLA Target": data.get("met", 0),
                "Breached SLA": data.get("breached", 0),
                "Achievement %": f"{data.get('achievement_pct', '0')}%",
                "Breaching Incident IDs": ", ".join(data.get("breach_ids", [])) or "None",
            })
        st.dataframe(pd.DataFrame(bd_rows), use_container_width=True)
    else:
        st.info("No incident records available for this vendor.")

# TAB 4: LICENCE UTILISATION
with tab_util:
    st.subheader("Licence Usage & Over-Purchasing Analysis")
    st.write(f"Monthly active seats compared against total purchased licences (Threshold: {low_util_threshold}%).")
    
    usage_file = BASE_DIR / "data" / "usage.csv"
    if usage_file.exists():
        df_usage = pd.read_csv(usage_file)
        v_usage = df_usage[df_usage["vendor"] == vendor_name]
        if not v_usage.empty:
            st.dataframe(v_usage, use_container_width=True)
            chart_df = v_usage[["month", "licences_purchased", "licences_active"]].set_index("month")
            st.line_chart(chart_df)
        else:
            st.info(f"No usage data found for {vendor_name}.")
    for n in util_info.get("recommendation_notes", []):
        st.info(n)

# TAB 5: CONTRACT TERMS
with tab_contract:
    st.subheader("Extracted Contractual Terms")
    contract_res = result.get("contract") or {}
    if contract_res.get("success"):
        terms_dict = contract_res.get("terms") or {}
        term_table = []
        for fld in ["vendor_name", "contract_start", "contract_end", "renewal_type", "notice_period_days", "notice_deadline", "annual_cost"]:
            f_obj = terms_dict.get(fld, {})
            term_table.append({
                "Contract Field": fld.replace("_", " ").title(),
                "Extracted Value": f_obj.get("value", "NOT FOUND"),
                "Confidence": f_obj.get("confidence", "NOT_FOUND"),
                "Supporting Evidence": f_obj.get("evidence", "")[:120] + "..." if f_obj.get("evidence") else "",
            })
        st.dataframe(pd.DataFrame(term_table), use_container_width=True)
    else:
        st.warning(f"Contract not loaded: {contract_res.get('error', 'No file specified')}")

# TAB 6: RAG CLAUSE SEARCH
with tab_search:
    st.subheader("🔍 Local Contract Clause Retriever (BM25 / Section Search)")
    st.write(f"Search for specific clauses or policies within the loaded contract for **{vendor_name}** under strict vendor isolation.")
    
    search_q = st.text_input("Enter search query (e.g. 'notice period', 'service credits', 'termination fee'):", "notice period")
    if st.button("Search Contract Clauses"):
        search_res = agent.search_contract(search_q, top_k=5)
        matches = search_res.get("matches", [])
        if matches:
            st.success(f"Found {len(matches)} matching clause chunk(s) across {search_res.get('total_chunks_searched')} indexed sections:")
            for m in matches:
                with st.expander(f"📌 {m['section']} [Relevance: {m['relevance']}, Score: {m['score']}]"):
                    if m.get("clause"):
                        st.caption(f"Clause: {m['clause']}")
                    st.code(m["content"])
        else:
            st.info("No matching clauses found for this query.")
            for w in search_res.get("warnings", []):
                st.warning(w)

# TAB 7: SAFEGUARDS
with tab_guardrails:
    st.subheader("Advisory Boundaries & Forbidden Actions Testing")
    st.write("Test conversational queries against the deterministic safety guardrails.")
    
    test_query = st.text_input(
        "Enter query or command to test safeguard:",
        "Please terminate contract VendorA immediately."
    )
    if st.button("Test Query Safety"):
        blocked_msg = check_forbidden_action(test_query)
        if blocked_msg:
            st.error("🛑 ACTION BLOCKED BY SAFEGUARD:")
            st.markdown(blocked_msg)
        else:
            st.success("✅ Query Allowed: This is an analytical / informational request.")
