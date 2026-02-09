import streamlit as st
from utils.auth import get_authenticator
from datetime import date, datetime, timedelta
import pandas as pd
from utils import database as db
from utils.database import (
    get_categories,
    get_transactions,
    get_budget_months,
    get_budget_targets,
    upsert_budget_target,
    delete_budget_target,
)

# Page configuration
st.set_page_config(
    page_title="Goals",
    page_icon="🎯",
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

# Helpers

def get_month_bounds(month_str: str) -> tuple[date, date]:
    year, month = [int(part) for part in month_str.split("-")]
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    return month_start, month_end

def get_transaction_months() -> list[str]:
    if hasattr(db, "get_transaction_months"):
        return db.get_transaction_months()

    transactions = get_transactions()
    months = {trans['date'][:7] for trans in transactions if trans.get('date')}
    return sorted(months, reverse=True)

# Main content
st.title("🎯 Monthly Goals")
st.markdown("Set monthly budgets per category and track your spending progress.")

current_month = datetime.now().strftime("%Y-%m")
month_options = []
for month in [current_month] + get_budget_months() + get_transaction_months():
    if month not in month_options:
        month_options.append(month)

selected_month = st.selectbox(
    "Month",
    options=month_options,
    index=0,
    help="Budgets and progress are tracked per calendar month"
)

month_start, month_end = get_month_bounds(selected_month)
month_from = month_start.strftime("%Y-%m-%d")
month_to = month_end.strftime("%Y-%m-%d")

# Fetch budgets and transactions
budget_targets = get_budget_targets(selected_month)
transactions = get_transactions(date_from=month_from, date_to=month_to)

# Budget setup
st.subheader("💾 Set Monthly Budgets")

categories = get_categories()

with st.form("budget_form"):
    overall_budget_value = float(budget_targets.get(None, 0.0))
    overall_budget = st.number_input(
        "Overall monthly budget (optional)",
        min_value=0.0,
        step=100.0,
        value=overall_budget_value,
        help="Total budget across all categories"
    )

    st.divider()
    st.markdown("**Category budgets**")

    category_inputs = {}
    if categories:
        for category in categories:
            current_value = float(budget_targets.get(category, 0.0))
            category_inputs[category] = st.number_input(
                category,
                min_value=0.0,
                step=100.0,
                value=current_value,
                key=f"budget_{selected_month}_{category}"
            )
    else:
        st.info("Add categories first to set category budgets.")

    save_budgets = st.form_submit_button("💾 Save Budgets", width="stretch", type="primary")

    if save_budgets:
        if overall_budget > 0:
            upsert_budget_target(selected_month, None, overall_budget)
        else:
            delete_budget_target(selected_month, None)

        for category, amount in category_inputs.items():
            if amount > 0:
                upsert_budget_target(selected_month, category, amount)
            else:
                delete_budget_target(selected_month, category)

        st.success("✅ Budgets saved")
        st.rerun()

st.divider()

# Build summary
st.subheader("📊 Monthly Summary")

if transactions:
    df = pd.DataFrame(transactions)
    df['date'] = pd.to_datetime(df['date'])
    total_spent = df['amount'].sum()
else:
    df = pd.DataFrame(columns=['date', 'description', 'category', 'amount', 'account'])
    total_spent = 0.0

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Spent", f"₱{total_spent:,.2f}")

with col2:
    if overall_budget > 0:
        st.metric("Overall Budget", f"₱{overall_budget:,.2f}")
    else:
        st.metric("Overall Budget", "Not set")

with col3:
    if overall_budget > 0:
        remaining = overall_budget - total_spent
        st.metric("Remaining", f"₱{remaining:,.2f}")
    else:
        st.metric("Remaining", "-")

if overall_budget > 0:
    usage_pct = (total_spent / overall_budget) * 100
    if total_spent > overall_budget:
        st.error(f"🚨 Over limit: {usage_pct:.0f}% used")
    elif usage_pct >= 80:
        st.warning(f"⚠️ Near limit: {usage_pct:.0f}% used")
    else:
        st.success(f"✅ On track: {usage_pct:.0f}% used")
else:
    st.info("Set an overall budget to track monthly limits.")

st.divider()

# Category budget table
st.subheader("🏷️ Category Progress")

category_spend = df.groupby('category')['amount'].sum().to_dict()
category_rows = []

all_categories = sorted(set(category_spend.keys()) | set(budget_targets.keys()) - {None})

for category in all_categories:
    budget = float(budget_targets.get(category, 0.0))
    spent = float(category_spend.get(category, 0.0))
    remaining = budget - spent if budget > 0 else 0.0
    usage_pct = (spent / budget) * 100 if budget > 0 else None

    if budget == 0 and spent == 0:
        continue

    if budget == 0:
        status = "No budget"
    elif spent > budget:
        status = "Over limit"
    elif usage_pct is not None and usage_pct >= 80:
        status = "Near limit"
    else:
        status = "On track"

    category_rows.append({
        "Category": category,
        "Budget": budget,
        "Spent": spent,
        "Remaining": remaining,
        "Usage": f"{usage_pct:.0f}%" if usage_pct is not None else "-",
        "Status": status
    })

if category_rows:
    category_df = pd.DataFrame(category_rows)
    category_df = category_df.sort_values(by="Spent", ascending=False)
    category_df['Budget'] = category_df['Budget'].apply(lambda x: f"₱{x:,.2f}" if x > 0 else "-")
    category_df['Spent'] = category_df['Spent'].apply(lambda x: f"₱{x:,.2f}")
    category_df['Remaining'] = category_df['Remaining'].apply(lambda x: f"₱{x:,.2f}" if x != 0 else "-")
    st.dataframe(category_df, width="stretch", hide_index=True)
else:
    st.info("No category budgets or spending for this month yet.")

st.divider()

# Top expenses per category
st.subheader("🔝 Top Expenses by Category")

if df.empty:
    st.info("No transactions yet for this month.")
else:
    available_categories = sorted(df['category'].unique())
    selected_category = st.selectbox(
        "Category",
        options=available_categories,
        help="See the largest transactions for the selected category"
    )

    category_transactions = df[df['category'] == selected_category].copy()
    category_transactions = category_transactions.sort_values(by='amount', ascending=False).head(10)

    if category_transactions.empty:
        st.info("No transactions found for this category.")
    else:
        category_transactions['date'] = category_transactions['date'].dt.strftime('%Y-%m-%d')
        category_transactions['amount'] = category_transactions['amount'].apply(lambda x: f"₱{x:,.2f}")
        display_df = category_transactions[['date', 'description', 'amount', 'account']]
        display_df.columns = ['Date', 'Description', 'Amount', 'Account']
        st.dataframe(display_df, width="stretch", hide_index=True)

st.divider()

st.markdown(
    "Budgets reset every calendar month. Use the month selector above to review past months."
)
