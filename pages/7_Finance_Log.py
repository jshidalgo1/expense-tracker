import streamlit as st
from utils.auth import get_authenticator
from datetime import date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import database as db

# Page configuration
st.set_page_config(
    page_title="Finance Log",
    page_icon="💼",
    layout="wide"
)

# Authentication check - Load config from Streamlit secrets
authenticator = get_authenticator()

try:
    authenticator.login()
except Exception as e:
    st.error(e)

if not st.session_state.get('authentication_status'):
    st.warning("Please login from the main page")
    st.stop()

st.title("💼 Overall Finance Log")
st.markdown("Log your total bank balances and debt per cutoff to track net worth over time.")

st.subheader("🧾 Log Overall Finance")

asset_template = pd.DataFrame([{"Bank": "", "Amount": 0.0}])
debt_template = pd.DataFrame([{"Debt": "", "Amount": 0.0}])

assets_data_key = "finance_assets_data"
debts_data_key = "finance_debts_data"
assets_editor_key = "finance_assets_editor"
debts_editor_key = "finance_debts_editor"

if assets_data_key not in st.session_state:
    existing_assets = db.get_finance_current_items("asset")
    if existing_assets:
        st.session_state[assets_data_key] = pd.DataFrame(existing_assets).rename(
            columns={"name": "Bank", "amount": "Amount"}
        )
    else:
        st.session_state[assets_data_key] = asset_template

if debts_data_key not in st.session_state:
    existing_debts = db.get_finance_current_items("debt")
    if existing_debts:
        st.session_state[debts_data_key] = pd.DataFrame(existing_debts).rename(
            columns={"name": "Debt", "amount": "Amount"}
        )
    else:
        st.session_state[debts_data_key] = debt_template

col_assets, col_debts = st.columns(2)

with col_assets:
    st.markdown("**Bank Accounts**")
    if st.button("Add bank row"):
        st.session_state[assets_data_key] = pd.concat(
            [st.session_state[assets_data_key], asset_template],
            ignore_index=True
        )

with col_debts:
    st.markdown("**Debts**")
    if st.button("Add debt row"):
        st.session_state[debts_data_key] = pd.concat(
            [st.session_state[debts_data_key], debt_template],
            ignore_index=True
        )

st.caption("Edit rows below, then click Save Rows.")

def build_items(df: pd.DataFrame, name_col: str) -> list[tuple[str, float]]:
    if df.empty or name_col not in df.columns:
        return []
    cleaned = df.copy()
    cleaned[name_col] = cleaned[name_col].fillna("").astype(str).str.strip()
    cleaned["Amount"] = pd.to_numeric(cleaned.get("Amount", 0.0), errors="coerce").fillna(0)
    filtered = cleaned[(cleaned[name_col] != "") | (cleaned["Amount"] != 0)]
    return [(row[name_col], float(row["Amount"])) for _, row in filtered.iterrows()]

with st.form("finance_rows_form"):
    rows_col_a, rows_col_b = st.columns(2)

    with rows_col_a:
        st.markdown("**Edit Banks**")
        assets_df = st.data_editor(
            st.session_state[assets_data_key],
            num_rows="dynamic",
            width="stretch",
            column_config={
                "Bank": st.column_config.TextColumn(required=False),
                "Amount": st.column_config.NumberColumn(min_value=0.0, step=0.01, format="%.2f")
            },
            hide_index=True,
            key=assets_editor_key
        )

    with rows_col_b:
        st.markdown("**Edit Debts**")
        debts_df = st.data_editor(
            st.session_state[debts_data_key],
            num_rows="dynamic",
            width="stretch",
            column_config={
                "Debt": st.column_config.TextColumn(required=False),
                "Amount": st.column_config.NumberColumn(min_value=0.0, step=0.01, format="%.2f")
            },
            hide_index=True,
            key=debts_editor_key
        )

    save_rows = st.form_submit_button("Save Rows", type="primary", width="stretch")
    if save_rows:
        st.session_state[assets_data_key] = assets_df
        st.session_state[debts_data_key] = debts_df
        db.replace_finance_current_items(
            "asset",
            build_items(st.session_state[assets_data_key], "Bank")
        )
        db.replace_finance_current_items(
            "debt",
            build_items(st.session_state[debts_data_key], "Debt")
        )
        st.success("✅ Rows saved")

assets_total = pd.to_numeric(
    st.session_state[assets_data_key].get("Amount", 0.0),
    errors="coerce"
).fillna(0).sum()

debts_total = pd.to_numeric(
    st.session_state[debts_data_key].get("Amount", 0.0),
    errors="coerce"
).fillna(0).sum()

net_worth = assets_total - debts_total


with st.form("finance_log_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        log_date = st.date_input("Log date", value=date.today())

    with col2:
        st.metric("Total assets", f"₱{assets_total:,.2f}")

    with col3:
        st.metric("Total debt", f"₱{debts_total:,.2f}")

    st.caption(f"Net worth: ₱{net_worth:,.2f}")

    submit_log = st.form_submit_button("Log Overall Finance", type="primary", width="stretch")

    if submit_log:
        asset_items = build_items(st.session_state[assets_data_key], "Bank")
        debt_items = build_items(st.session_state[debts_data_key], "Debt")
        if hasattr(db, "add_finance_log_with_items"):
            db.add_finance_log_with_items(
                log_date.strftime("%Y-%m-%d"),
                assets_total,
                debts_total,
                asset_items,
                debt_items
            )
        else:
            db.add_finance_log(log_date.strftime("%Y-%m-%d"), assets_total, debts_total)
            st.info("Saved totals only. Update the app to store per-bank breakdowns.")
        st.success("✅ Finance log saved")
        st.rerun()

st.divider()

st.subheader("📊 Finance History")

logs = db.get_finance_logs()

if not logs:
    st.info("No finance logs yet. Add your first log above.")
    st.stop()

df = pd.DataFrame(logs)
df['log_date'] = pd.to_datetime(df['log_date'])
df['growth_rate'] = df['net_worth'].pct_change() * 100

log_ids = df['id'].tolist()
items_df = pd.DataFrame()
if hasattr(db, "get_finance_log_items"):
    items = db.get_finance_log_items(log_ids)
    items_df = pd.DataFrame(items)

history = pd.DataFrame({
    "Date": df['log_date'].dt.strftime("%Y-%m-%d"),
    "Total Assets": df['total_assets'].map(lambda v: f"₱{v:,.2f}"),
    "Total Debt": df['total_debt'].map(lambda v: f"₱{v:,.2f}"),
    "Net Worth": df['net_worth'].map(lambda v: f"₱{v:,.2f}"),
    "Growth Rate": df['growth_rate'].map(lambda v: "-" if pd.isna(v) else f"{v:,.2f}%"),
})

st.dataframe(history, width="stretch", hide_index=True)

st.subheader("🗑️ Delete a Log")
log_options = [
    {
        "label": f"{row['log_date'].strftime('%Y-%m-%d')} — ₱{row['net_worth']:,.2f}",
        "id": int(row['id'])
    }
    for _, row in df.iterrows()
]

selected_label = st.selectbox(
    "Select a log to delete",
    options=[opt["label"] for opt in log_options]
)

selected_log_id = next(
    opt["id"] for opt in log_options if opt["label"] == selected_label
)

confirm_delete = st.checkbox("I understand this will permanently delete the log")

if st.button("Delete selected log", type="primary", disabled=not confirm_delete):
    if db.delete_finance_log(selected_log_id):
        st.success("✅ Log deleted")
        st.rerun()
    st.error("Log not found. Please refresh and try again.")

st.subheader("🧩 Breakdown per Log")
if items_df.empty:
    st.info("No breakdown items saved yet.")
else:
    for _, row in df.iterrows():
        log_id = int(row['id'])
        label = row['log_date'].strftime("%Y-%m-%d")
        with st.expander(f"{label} — Net worth: ₱{row['net_worth']:,.2f}"):
            log_items = items_df[items_df['log_id'] == log_id]
            assets_items = log_items[log_items['item_type'] == 'asset']
            debts_items = log_items[log_items['item_type'] == 'debt']

            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("**Assets**")
                if assets_items.empty:
                    st.caption("No assets recorded.")
                else:
                    st.dataframe(
                        assets_items[['name', 'amount']]
                            .rename(columns={'name': 'Bank', 'amount': 'Amount (₱)'}),
                        width="stretch",
                        hide_index=True
                    )

            with col_b:
                st.markdown("**Debts**")
                if debts_items.empty:
                    st.caption("No debts recorded.")
                else:
                    st.dataframe(
                        debts_items[['name', 'amount']]
                            .rename(columns={'name': 'Debt', 'amount': 'Amount (₱)'}),
                        width="stretch",
                        hide_index=True
                    )

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Net Worth Over Time")
    fig_net = px.line(
        df,
        x='log_date',
        y='net_worth',
        markers=True,
        labels={'log_date': 'Date', 'net_worth': 'Net Worth (₱)'},
        title=""
    )
    fig_net.update_traces(
        line_color='#1f77b4',
        line_width=3,
        marker_size=8,
        hovertemplate='<b>%{x|%Y-%m-%d}</b><br>₱%{y:,.2f}<extra></extra>'
    )
    fig_net.update_layout(height=350)
    st.plotly_chart(fig_net, use_container_width=True)

with col2:
    st.subheader("🏦 Assets vs Debt")
    long_df = df.melt(
        id_vars=['log_date'],
        value_vars=['total_assets', 'total_debt'],
        var_name='type',
        value_name='amount'
    )
    long_df['type'] = long_df['type'].map({
        'total_assets': 'Assets',
        'total_debt': 'Debt'
    })

    fig_assets = px.bar(
        long_df,
        x='log_date',
        y='amount',
        color='type',
        barmode='group',
        labels={'log_date': 'Date', 'amount': 'Amount (₱)', 'type': ''},
        title=""
    )
    fig_assets.update_traces(
        hovertemplate='<b>%{x|%Y-%m-%d}</b><br>₱%{y:,.2f}<extra></extra>'
    )
    fig_assets.update_layout(height=350, legend_title_text="")
    st.plotly_chart(fig_assets, use_container_width=True)

st.subheader("📉 Growth Rate Over Time")

fig_growth = go.Figure()
fig_growth.add_trace(go.Scatter(
    x=df['log_date'],
    y=df['growth_rate'],
    mode='lines+markers',
    line=dict(color='#2ca02c', width=3),
    marker=dict(size=8),
    hovertemplate='<b>%{x|%Y-%m-%d}</b><br>%{y:.2f}%<extra></extra>'
))
fig_growth.add_hline(y=0, line_dash="dash", line_color="#999999")
fig_growth.update_layout(
    height=300,
    xaxis_title="Date",
    yaxis_title="Growth Rate (%)",
    title=""
)

st.plotly_chart(fig_growth, use_container_width=True)
