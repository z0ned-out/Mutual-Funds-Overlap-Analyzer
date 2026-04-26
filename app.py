import streamlit as st
import pandas as pd
import requests

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(layout="wide")

# -------------------------------
# HELPER
# -------------------------------
def center_heading(text, level=2):
    return f"<h{level} style='text-align:center; margin-top:20px;'>{text}</h{level}>"

def fund_label(name):
    return f"<div style='text-align:center; font-size:13px; font-weight:600; margin-bottom:6px;'>{name}</div>"

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxJugJaU6FR5M93sxZn-JlYgP2X-7VbHmcFH-6uDc3CqKHJXXIfanbCaUYZyLNFiib_/exec"

# -------------------------------
# FETCH HOLDINGS
# -------------------------------
@st.cache_data(show_spinner=False)
def fetch_holdings(url):
    response = requests.get(APPS_SCRIPT_URL, params={"url": url})
    data = response.json()

    if isinstance(data, dict) and "error" in data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    df = df.rename(columns={
        "name": "Name",
        "type": "Type",
        "aum": "AUM",
        "weight": "Weight"
    })

    df["AUM"] = pd.to_numeric(df["AUM"], errors="coerce")
    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce") * 100

    return df

# -------------------------------
# LOAD FUNDS
# -------------------------------
@st.cache_data
def load_funds():
    return pd.read_csv("mf_funds.csv")

# -------------------------------
# SUMMARY
# -------------------------------
def get_type_summary(df):
    summary = (
        df.groupby("Type")
        .agg(
            Total_AUM=("AUM", "sum"),
            Total_Weight=("Weight", "sum")
        )
        .reset_index()
    )

    total_row = pd.DataFrame({
        "Type": ["Total"],
        "Total_AUM": [summary["Total_AUM"].sum()],
        "Total_Weight": [summary["Total_Weight"].sum()]
    })

    return pd.concat([summary, total_row], ignore_index=True)

# -------------------------------
# ALIGN
# -------------------------------
def align_summaries(s1, s2):
    types = sorted(set(s1["Type"]).union(set(s2["Type"])))

    if "Total" in types:
        types.remove("Total")
        types.append("Total")

    def fix(df):
        return df.set_index("Type").reindex(types).reset_index()

    return fix(s1), fix(s2)

# -------------------------------
# COMMON HOLDINGS
# -------------------------------
def get_common_holdings(df1, df2):
    df1_eq = df1[df1["Type"] == "Equity"].copy()
    df2_eq = df2[df2["Type"] == "Equity"].copy()

    df1_eq.rename(columns={"Weight": "Weight_1", "AUM": "AUM_1"}, inplace=True)
    df2_eq.rename(columns={"Weight": "Weight_2", "AUM": "AUM_2"}, inplace=True)

    merged = pd.merge(df1_eq, df2_eq, on="Name", how="inner")

    return merged[["Name", "Weight_1", "Weight_2", "AUM_1", "AUM_2"]]

# -------------------------------
# METRICS
# -------------------------------
def compute_metrics(df, common_df, fund_id):

    df_eq = df[df["Type"] == "Equity"]

    total_aum = df["AUM"].sum()
    equity_aum = df_eq["AUM"].sum()
    equity_weight = df_eq["Weight"].sum()

    if common_df is not None and not common_df.empty:
        if fund_id == 1:
            common_aum = common_df["AUM_1"].sum()
        else:
            common_aum = common_df["AUM_2"].sum()
        common_stocks = len(common_df)
    else:
        common_aum = 0
        common_stocks = 0

    if equity_aum > 0:
        common_weight_pct = (common_aum / equity_aum) * 100
    else:
        common_weight_pct = 0

    overlap_amount = (common_weight_pct * equity_weight) / 100

    return {
        "Total Stocks": len(df),
        "Equity Stocks": len(df_eq),
        "Common Stocks": common_stocks,
        "Total AUM": total_aum,
        "Equity AUM": equity_aum,
        "Common AUM": common_aum,
        "Equity Allocation %": equity_weight,
        "Common Stock Overlap %": common_weight_pct,
        "Overlap Amount (Base 100 INR)": overlap_amount
    }

def metrics_to_df(metrics):
    df = pd.DataFrame({
        "Metric": list(metrics.keys()),
        "Value": list(metrics.values())
    })
    df = df.dropna()
    df["Value"] = df["Value"].apply(lambda x: round(x, 2))
    return df

# -------------------------------
# UI
# -------------------------------
st.title("Mutual Fund Analyzer")
st.caption("All AUM figures are in ₹ Cr")
st.caption("All weights in %")

df = load_funds()
fund_map = dict(zip(df["Fund Name"], df["URL"]))
fund_names = sorted(fund_map.keys())

col1, col2 = st.columns(2)

with col1:
    fund1 = st.selectbox("Select Fund 1", fund_names, index=None, placeholder="Type or select a fund")

with col2:
    fund2 = st.selectbox("Select Fund 2", fund_names, index=None, placeholder="Type or select a fund")

# -------------------------------
# MAIN LOGIC
# -------------------------------
if fund1 and fund2:

    df1 = fetch_holdings(fund_map[fund1])[["Name", "Type", "AUM", "Weight"]]
    df2 = fetch_holdings(fund_map[fund2])[["Name", "Type", "AUM", "Weight"]]

    summary1 = get_type_summary(df1)
    summary2 = get_type_summary(df2)
    summary1, summary2 = align_summaries(summary1, summary2)

    common_df = get_common_holdings(df1, df2)

    metrics1 = compute_metrics(df1, common_df, 1)
    metrics2 = compute_metrics(df2, common_df, 2)

    # -------------------------------
    # FINAL OVERLAP
    # -------------------------------
    overlap_a = metrics1["Overlap Amount (Base 100 INR)"]
    overlap_b = metrics2["Overlap Amount (Base 100 INR)"]

    equity_a = metrics1["Equity Allocation %"]
    equity_b = metrics2["Equity Allocation %"]

    total_equity_invested = equity_a + equity_b

    final_overlap = (overlap_a + overlap_b) / total_equity_invested if total_equity_invested > 0 else 0

    # -------------------------------
    # METRICS TABLE
    # -------------------------------
    st.markdown(center_heading("Fund Comparison Metrics", 2), unsafe_allow_html=True)

    m1, m2 = st.columns(2)
    with m1:
        st.markdown(fund_label(fund1), unsafe_allow_html=True)
        st.dataframe(metrics_to_df(metrics1), width="stretch", hide_index=True)
    with m2:
        st.markdown(fund_label(fund2), unsafe_allow_html=True)
        st.dataframe(metrics_to_df(metrics2), width="stretch", hide_index=True)

    # -------------------------------
    # FINAL OVERLAP TABLE
    # -------------------------------
    st.markdown(center_heading("Final Overlap (₹100 + ₹100 Basis)", 2), unsafe_allow_html=True)

    final_df = pd.DataFrame({
        "Metric": ["Fund A Overlap", "Fund B Overlap", "Final Overlap %"],
        "Value": [round(overlap_a,2), round(overlap_b,2), round(final_overlap*100,2)]
    })

    st.dataframe(final_df, hide_index=True, width="stretch")

    # -------------------------------
    # SUMMARY
    # -------------------------------
    st.markdown(center_heading("Allocation Summary", 3), unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(fund_label(fund1), unsafe_allow_html=True)
        st.dataframe(summary1, width="stretch")

    with c2:
        st.markdown(fund_label(fund2), unsafe_allow_html=True)
        st.dataframe(summary2, width="stretch")
    
    
    # -------------------------------
    # HOLDINGS
    # -------------------------------
    st.markdown(center_heading("Holdings", 3), unsafe_allow_html=True)

    h1, h2 = st.columns(2)
    with h1:
        st.markdown(fund_label(fund1), unsafe_allow_html=True)
        st.dataframe(df1, height=400, width="stretch")

    with h2:
        st.markdown(fund_label(fund2), unsafe_allow_html=True)
        st.dataframe(df2, height=400, width="stretch")

    # -------------------------------
    # COMMON HOLDINGS
    # -------------------------------
    st.markdown(
    f"<div style='text-align:center; font-size:13px; margin-bottom:6px;'>{fund1}  vs  {fund2}</div>",
    unsafe_allow_html=True
)

    if not common_df.empty:
        st.dataframe(common_df, width="stretch", height=400)
    else:
        st.info("No common equity holdings")
