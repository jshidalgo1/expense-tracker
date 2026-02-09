import streamlit as st
from utils.auth import get_authenticator
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, date
from utils.database import get_transactions, get_date_range, get_budget_targets
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
    default_end = today
    default_start = today - timedelta(days=30)

    min_value = datetime.strptime(min_date_str, "%Y-%m-%d").date() if min_date_str else None
    max_value = datetime.strptime(max_date_str, "%Y-%m-%d").date() if max_date_str else None

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

# Breakdowns
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Spending by Category")
    category_spending = df.groupby('category')['amount'].sum().sort_values(ascending=False)

    fig_category = px.pie(
        values=category_spending.values,
        names=category_spending.index,
        title="",
        hole=0.4
    )
    fig_category.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>₱%{value:,.2f}<br>%{percent}<extra></extra>'
    )
    fig_category.update_layout(showlegend=True, height=360)
    st.plotly_chart(fig_category, width="stretch")

with col2:
    st.subheader("💳 Spending by Account")
    account_spending = df.groupby('account')['amount'].sum().sort_values(ascending=False)

    fig_account = px.bar(
        x=account_spending.index,
        y=account_spending.values,
        title="",
        labels={'x': 'Account', 'y': 'Amount (₱)'},
        color=account_spending.values,
        color_continuous_scale='Blues'
    )
    fig_account.update_traces(
        hovertemplate='<b>%{x}</b><br>₱%{y:,.2f}<extra></extra>'
    )
    fig_account.update_layout(
        showlegend=False,
        height=360,
        xaxis_title="Account Type",
        yaxis_title="Amount (₱)"
    )
    st.plotly_chart(fig_account, width="stretch")

st.divider()

# Top expenses
st.subheader("🔝 Top Expenses")

top_expenses = df.nlargest(10, 'amount')[['date', 'description', 'category', 'amount']]
top_expenses['date'] = top_expenses['date'].dt.strftime('%Y-%m-%d')
top_expenses['amount'] = top_expenses['amount'].apply(lambda x: f"₱{x:,.2f}")
top_expenses.columns = ['Date', 'Description', 'Category', 'Amount']

st.dataframe(top_expenses, width="stretch", hide_index=True)

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

# Categorization health
st.divider()

st.subheader("🏷️ Categorization Health")

stats = get_learning_stats()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Transactions", stats['total_transactions'])

with col2:
    st.metric("Uncategorized", stats['uncategorized'])

with col3:
    st.metric("Pending Suggestions", stats['pending_suggestions'])

with col4:
    st.metric("Rule Coverage", f"{stats['coverage_percentage']:.1f}%")
