import streamlit as st
from utils.auth import get_authenticator
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from utils.database import (
    get_transactions,
    get_date_range,
    get_budget_targets,
    get_finance_logs
)
from utils.merchant_learner import get_learning_stats

# Page configuration
st.set_page_config(
    page_title="Summary",
    page_icon="🧾",
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


def get_month_bounds(month_str: str) -> tuple[date, date]:
    year, month = [int(part) for part in month_str.split("-")]
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    return month_start, month_end


st.title("🧾 Summary")

# Filters in sidebar
with st.sidebar:
    st.subheader("🔍 Filters")

    min_date_str, max_date_str = get_date_range()
    today = datetime.now().date()

    min_value = datetime.strptime(min_date_str, "%Y-%m-%d").date() if min_date_str else None
    max_value = datetime.strptime(max_date_str, "%Y-%m-%d").date() if max_date_str else None

    default_end = min(max_value, today) if max_value else today
    default_start = today - timedelta(days=30)

    if min_value and default_start < min_value:
        default_start = min_value
    if max_value and default_start > max_value:
        default_start = max_value

    date_range = st.date_input(
        "Date Range",
        value=(default_start, default_end),
        min_value=min_value,
        max_value=max_value,
        help="Default is last 30 days"
    )

if len(date_range) == 2:
    date_from = date_range[0].strftime("%Y-%m-%d")
    date_to = date_range[1].strftime("%Y-%m-%d")
else:
    date_from = None
    date_to = None

transactions = get_transactions(date_from=date_from, date_to=date_to)

if not transactions:
    st.info("📭 No transactions found for the selected date range.")
    st.stop()

df = pd.DataFrame(transactions)
df['date'] = pd.to_datetime(df['date'])

# Current month budget stats
current_month = datetime.now().strftime("%Y-%m")
month_start, month_end = get_month_bounds(current_month)
month_from = month_start.strftime("%Y-%m-%d")
month_to = month_end.strftime("%Y-%m-%d")

budget_targets = get_budget_targets(current_month)
monthly_transactions = get_transactions(date_from=month_from, date_to=month_to)

if monthly_transactions:
    month_df = pd.DataFrame(monthly_transactions)
    month_total = month_df['amount'].sum()
else:
    month_df = pd.DataFrame(columns=['category', 'amount'])
    month_total = 0.0

overall_budget = float(budget_targets.get(None, 0.0))

# At-a-glance visuals
st.subheader("✨ At a Glance")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.caption("This Month vs Budget")
    if overall_budget > 0:
        usage_pct = (month_total / overall_budget) * 100
        gauge_max = max(100, min(150, (int(usage_pct / 10) + 1) * 10))
        fig_budget = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=usage_pct,
                number={"suffix": "%"},
                gauge={
                    "axis": {"range": [0, gauge_max]},
                    "bar": {"color": "#1f77b4"},
                    "steps": [
                        {"range": [0, 80], "color": "#dfeaf7"},
                        {"range": [80, 100], "color": "#f6e6a6"},
                        {"range": [100, gauge_max], "color": "#f5c6cb"}
                    ],
                    "threshold": {
                        "line": {"color": "#d62728", "width": 3},
                        "thickness": 0.75,
                        "value": 100
                    }
                }
            )
        )
        fig_budget.update_layout(height=240, margin=dict(l=10, r=10, t=25, b=10))
        st.plotly_chart(fig_budget, width="stretch")
        st.caption(f"₱{month_total:,.0f} of ₱{overall_budget:,.0f}")
    else:
        st.info("Set an overall budget in Goals to track this gauge.")
        st.metric("Spent This Month", f"₱{month_total:,.2f}")

with col2:
    st.caption("Category Share")
    category_spending = df.groupby('category')['amount'].sum().sort_values(ascending=False)
    if len(category_spending) > 5:
        top_categories = category_spending.head(5)
        other_total = category_spending.iloc[5:].sum()
        category_spending = pd.concat([top_categories, pd.Series({'Other': other_total})])
    fig_category = px.pie(
        values=category_spending.values,
        names=category_spending.index,
        hole=0.5
    )
    fig_category.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>₱%{value:,.2f}<br>%{percent}<extra></extra>'
    )
    fig_category.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_category, width="stretch")

with col3:
    st.caption("Account Split")
    account_spending = df.groupby('account')['amount'].sum().sort_values(ascending=False)
    account_df = account_spending.reset_index()
    account_df.columns = ['Account', 'Amount']
    account_df['Percent'] = (account_df['Amount'] / account_df['Amount'].sum()) * 100
    fig_account = px.bar(
        account_df,
        x='Account',
        y='Percent',
        text=account_df['Percent'].map(lambda x: f"{x:.0f}%"),
        labels={'Percent': 'Percent'}
    )
    fig_account.update_traces(hovertemplate='<b>%{x}</b><br>%{y:.1f}%<extra></extra>')
    fig_account.update_layout(
        height=240,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(range=[0, 100], ticksuffix='%')
    )
    st.plotly_chart(fig_account, width="stretch")

with col4:
    st.caption("Auto-Categorization")
    learning_stats = get_learning_stats()
    coverage_pct = learning_stats.get('coverage_percentage', 0.0)
    st.metric("Coverage", f"{coverage_pct:.0f}%")
    st.progress(min(coverage_pct / 100, 1.0))
    st.caption(
        f"{learning_stats.get('transactions_covered_by_mapping', 0):,} of "
        f"{learning_stats.get('total_transactions', 0):,} txns"
    )

st.divider()

# Trend line
st.subheader("📈 Spending Trend")

daily_spending = df.groupby(df['date'].dt.date)['amount'].sum().reset_index()
daily_spending.columns = ['Date', 'Amount']
daily_spending['Rolling7'] = daily_spending['Amount'].rolling(7, min_periods=1).mean()

fig_trend = px.line(
    daily_spending,
    x='Date',
    y=['Amount', 'Rolling7'],
    labels={'value': 'Amount (₱)', 'variable': 'Series'}
)
fig_trend.update_traces(hovertemplate='₱%{y:,.2f}<extra></extra>')
fig_trend.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig_trend, width="stretch")

# Finance summary
st.divider()

st.subheader("💼 Finance Summary")

logs = get_finance_logs()

if not logs:
    st.info("No finance logs yet. Add a log in Finance Log to see your net worth summary here.")
else:
    latest = logs[-1]
    previous = logs[-2] if len(logs) > 1 else None
    delta_net_worth = None
    if previous:
        delta_net_worth = latest['net_worth'] - previous['net_worth']

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Assets", f"₱{latest['total_assets']:,.2f}")

    with col2:
        st.metric("Total Debt", f"₱{latest['total_debt']:,.2f}")

    with col3:
        delta_label = f"₱{delta_net_worth:,.2f}" if delta_net_worth is not None else None
        st.metric("Net Worth", f"₱{latest['net_worth']:,.2f}", delta_label)

    st.caption(f"Latest log: {latest['log_date']}")
