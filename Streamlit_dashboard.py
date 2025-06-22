import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ---- CONFIG ----
FILE = "model_202402191144_eval_20240102_through_20240306_DF-Positions.txt"

# ---- LOAD DATA ----
df = pd.read_csv(FILE, parse_dates=["Time"])
df.set_index("Time", inplace=True)
date_list = sorted([d.to_pydatetime().date() for d in df.index.unique()])
tickers = df.columns.tolist()

# ---- HELPERS ----
pct = lambda x: f"{x:.2%}"

def get_equal_weight_targets(snapshot):
    non_cash = [t for t in snapshot.index if t.lower() != "cash"]
    equal_wt = 1 / len(non_cash) if non_cash else 0
    return {t: (0.0 if t.lower() == "cash" else equal_wt) for t in snapshot.index}

# ---- HEADER ----
st.title("📊 Portfolio Dashboard")

# ---- SUMMARY SECTION ----
selected_date = st.slider(
    "Select Date for Snapshot",
    min_value=min(date_list),
    max_value=max(date_list),
    value=max(date_list),
    format="YYYY-MM-DD"
)
snapshot = df.loc[pd.to_datetime(selected_date)]
TARGET_WEIGHTS = get_equal_weight_targets(snapshot)

st.markdown("### Summary")
st.markdown(f"- **Date**: {selected_date.strftime('%Y-%m-%d')}")
st.markdown(f"- **Portfolio Value**: ${50_000:,.0f}")
st.markdown(f"- **Cash %**: {pct(snapshot['Cash']) if 'Cash' in snapshot else '—'}")

drift = (snapshot - pd.Series(TARGET_WEIGHTS))
needs_rebal = (drift.abs() > 0.02).any()
st.markdown(f"- **Needs Rebalance**: {'Yes' if needs_rebal else 'No'}")

# ---- PIE CHART SECTION ----
st.markdown("### Allocation Pie")
pie_date = st.slider(
    "Select Date for Pie Chart",
    min_value=min(date_list),
    max_value=max(date_list),
    value=max(date_list),
    format="YYYY-MM-DD",
    key="pie_date"
)
pie_snapshot = df.loc[pd.to_datetime(pie_date)]

pie_fig = px.pie(
    pie_snapshot.reset_index().rename(columns={"index": "Ticker", 0: "Weight"}),
    names=pie_snapshot.index,
    values=pie_snapshot.values,
    hole=0.45
)
pie_fig.update_traces(textposition="inside", texttemplate="%{label}<br>%{percent:.1%}")
st.plotly_chart(pie_fig)

# ---- ALLOCATION TABLE ----
st.markdown("### Allocation Table")
table_date = st.slider(
    "Select Date for Table",
    min_value=min(date_list),
    max_value=max(date_list),
    value=max(date_list),
    format="YYYY-MM-DD",
    key="table_date"
)
table_snapshot = df.loc[pd.to_datetime(table_date)]
TARGET_WEIGHTS = get_equal_weight_targets(table_snapshot)

table_df = table_snapshot.to_frame("Current")
table_df["Target"] = pd.Series(TARGET_WEIGHTS)
table_df["Drift"] = table_df["Current"] - table_df["Target"]
table_df["Current%"] = table_df["Current"].apply(pct)
table_df["Target%"] = table_df["Target"].apply(pct)
table_df["$"] = (table_df["Current"] * 50_000).round(2)
st.dataframe(table_df[["Current%", "Target%", "Drift", "$"]])

# ---- ALLOCATION HISTORY ----
TOP_N = 8
top_cols = snapshot.sort_values(ascending=False).head(TOP_N).index
hist = df[top_cols]

st.markdown("### Allocation History")
stack = px.area(hist.reset_index(), x="Time", y=top_cols,
                labels={"value": "Weight", "variable": "Ticker"},
                title="Allocation History")
stack.update_yaxes(tickformat=".0%", range=[0, 1])
st.plotly_chart(stack)

# ---- DRIFT MONITOR ----
st.markdown("### Drift Monitor")
drift_date = st.slider(
    "Select Date for Drift Monitor",
    min_value=min(date_list),
    max_value=max(date_list),
    value=max(date_list),
    format="YYYY-MM-DD",
    key="drift_date"
)
drift_band_local = st.slider("Drift Threshold", 0.0, 0.1, 0.02, step=0.005, key="drift_slider")
drift_snapshot = df.loc[pd.to_datetime(drift_date)]
TARGET_WEIGHTS = get_equal_weight_targets(drift_snapshot)

drift_df = drift_snapshot.to_frame("Current")
drift_df["Target"] = pd.Series(TARGET_WEIGHTS)
drift_df["Drift"] = drift_df["Current"] - drift_df["Target"]

bar = go.Figure(go.Bar(
    x=drift_df["Drift"].values,
    y=drift_df.index,
    orientation='h',
    marker_color=[
        'red' if abs(x) > drift_band_local else
        'orange' if abs(x) > drift_band_local * 0.5 else 'green'
        for x in drift_df["Drift"]
    ],
))
bar.add_vline(x=0, line_width=1, line_color="black")
bar.update_layout(height=600, xaxis_tickformat=".1%")
st.plotly_chart(bar)

# ---- TRADE SUGGESTIONS ----
st.markdown("### Trade Suggestions")
trade_date = st.slider(
    "Select Date for Trade Suggestions",
    min_value=min(date_list),
    max_value=max(date_list),
    value=max(date_list),
    format="YYYY-MM-DD",
    key="trade_date"
)
drift_band_trade = st.slider("Trade Drift Band", 0.0, 0.1, 0.02, step=0.005, key="trade_drift")
portfolio_val_trade = st.number_input("Portfolio Value for Trades", value=50_000, step=500)

trade_snapshot = df.loc[pd.to_datetime(trade_date)]
TARGET_WEIGHTS = get_equal_weight_targets(trade_snapshot)

dollar_drift = (trade_snapshot - pd.Series(TARGET_WEIGHTS)) * portfolio_val_trade
buy_actions, sell_actions = [], []

for t, dv in dollar_drift.items():
    if abs(dv) > portfolio_val_trade * drift_band_trade:
        action = "Buy" if dv < 0 else "Sell"
        line = f"{action} ${abs(dv):,.0f} {t}"
        if action == "Buy":
            buy_actions.append(line)
        else:
            sell_actions.append(line)

col1, col2 = st.columns(2)
with col1:
    st.subheader("📈 Buy")
    st.code("\n".join(buy_actions) if buy_actions else "No Buy suggestions.")
with col2:
    st.subheader("📉 Sell")
    st.code("\n".join(sell_actions) if sell_actions else "No Sell suggestions.")

# ---- DOWNLOAD TRADES ----
if buy_actions or sell_actions:
    combined_actions = "\n".join(buy_actions + sell_actions)
    st.download_button(
        label="💾 Download Trade Suggestions",
        data=combined_actions,
        file_name="trade_suggestions.txt",
        mime="text/plain"
    )
