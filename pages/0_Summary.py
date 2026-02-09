import streamlit as st
from utils.auth import get_authenticator
import pandas as pd
from datetime import datetime, timedelta, date
from utils.database import (
    get_transactions,
    get_date_range,
    get_budget_targets,
    get_finance_logs
)

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

# Spending overview
st.subheader("💰 Spending Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    total_expenses = df['amount'].sum()
    st.metric("Total Expenses", f"₱{total_expenses:,.2f}")

with col2:
    avg_transaction = df['amount'].mean()
    st.metric("Average Transaction", f"₱{avg_transaction:,.2f}")

with col3:
    transaction_count = len(df)
    st.metric("Total Transactions", f"{transaction_count:,}")

with col4:
    category_count = df['category'].nunique()
    st.metric("Categories Used", category_count)

st.divider()

# Budget status (current month)
st.subheader("🎯 Budget Status (Current Month)")

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

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Spent", f"₱{month_total:,.2f}")

with col2:
    st.metric("Overall Budget", f"₱{overall_budget:,.2f}" if overall_budget > 0 else "Not set")

with col3:
    if overall_budget > 0:
        remaining = overall_budget - month_total
        st.metric("Remaining", f"₱{remaining:,.2f}")
    else:
        st.metric("Remaining", "-")

if overall_budget > 0:
    usage_pct = (month_total / overall_budget) * 100
    if month_total > overall_budget:
        st.error(f"🚨 Over limit: {usage_pct:.0f}% used")
    elif usage_pct >= 80:
        st.warning(f"⚠️ Near limit: {usage_pct:.0f}% used")
    else:
        st.success(f"✅ On track: {usage_pct:.0f}% used")
else:
    st.info("Set an overall budget in Goals to track monthly limits.")

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
