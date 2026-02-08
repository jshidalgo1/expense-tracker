import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from utils.database import (
    get_transactions, get_categories, get_date_range,
    update_transaction_category, update_category,
    get_merchant_mappings, add_merchant_mapping, delete_merchant_mapping, update_merchant_mapping,
    find_similar_transactions, bulk_update_category
)

# Page configuration
st.set_page_config(
    page_title="Dashboard",
    page_icon="📊",
    layout="wide"
)

# Authentication check - Load config from YAML file
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    auto_hash=False
)

try:
    authenticator.login()
except Exception as e:
    st.error(e)

if not st.session_state.get('authentication_status'):
    st.warning("Please login from the main page")
    st.stop()

# Initialize refresh counter for data updates
if 'data_refresh_key' not in st.session_state:
    st.session_state.data_refresh_key = 0

# Main content
st.title("📊 Expense Dashboard")

# Filters in sidebar
with st.sidebar:
    st.subheader("🔍 Filters")
    
    # Date range filter
    # Date range filter
    min_date_str, max_date_str = get_date_range()
    
    if min_date_str and max_date_str:
        default_start = datetime.strptime(min_date_str, "%Y-%m-%d")
        default_end = datetime.strptime(max_date_str, "%Y-%m-%d")
    else:
        default_start = datetime.now() - timedelta(days=30)
        default_end = datetime.now()
        
    date_range = st.date_input(
        "Date Range",
        value=(default_start, default_end),
        help="Select date range for analysis"
    )
    
    # Category filter
    all_categories = get_categories()
    selected_categories = st.multiselect(
        "Categories",
        options=all_categories,
        default=all_categories,
        help="Filter by categories"
    )
    
    # Account filter
    all_accounts = ["Cash", "Bank", "Credit Card"]
    selected_accounts = st.multiselect(
        "Accounts",
        options=all_accounts,
        default=all_accounts,
        help="Filter by account type"
    )

# Get filtered transactions
if len(date_range) == 2:
    date_from = date_range[0].strftime("%Y-%m-%d")
    date_to = date_range[1].strftime("%Y-%m-%d")
else:
    date_from = None
    date_to = None

transactions = get_transactions(
    date_from=date_from,
    date_to=date_to,
    categories=selected_categories if selected_categories else None,
    accounts=selected_accounts if selected_accounts else None
)

# Check for uncategorized transactions
all_transactions_unfiltered = get_transactions()
uncategorized = [t for t in all_transactions_unfiltered if t.get('category') == 'Uncategorized']

# Show uncategorized mapping section if there are uncategorized transactions
if uncategorized:
    st.divider()
    st.subheader("🏷️ Map Uncategorized Transactions")
    st.markdown(f"You have **{len(uncategorized)}** uncategorized transaction(s). Map them to proper categories below.")
    
    # Add new category section
    with st.expander("➕ Add New Category", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            new_cat_name = st.text_input("Category Name", placeholder="e.g., Subscriptions, Rent, Gym", key="new_category_input")
        with col2:
            if st.button("➕ Add Category", width="stretch"):
                if new_cat_name and new_cat_name.strip():
                    from utils.categorizer import get_or_create_category
                    get_or_create_category(new_cat_name.strip())
                    st.success(f"✅ Category '{new_cat_name}' added!")
                    st.rerun()
                else:
                    st.error("❌ Please enter a category name")
    
    # Edit existing categories section
    with st.expander("✏️ Edit Categories", expanded=False):
        all_cats = get_categories()
        all_cats_filtered = [c for c in all_cats if c != "Uncategorized"]
        
        if all_cats_filtered:
            st.write("**Rename categories below:**")
            st.divider()
            
            for cat in sorted(all_cats_filtered):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    new_cat_name = st.text_input(
                        "New name",
                        value=cat,
                        key=f"edit_cat_{cat}",
                        label_visibility="collapsed"
                    )
                
                with col2:
                    if st.button("💾 Rename", key=f"btn_rename_{cat}", width="stretch"):
                        if new_cat_name and new_cat_name.strip() and new_cat_name != cat:
                            success = update_category(cat, new_cat_name.strip())
                            if success:
                                st.success(f"✅ Renamed '{cat}' to '{new_cat_name}'")
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to rename. Category might already exist.")
                        elif new_cat_name == cat:
                            st.info("ℹ️ No changes made")
                        else:
                            st.error("❌ Please enter a valid name")
        else:
            st.info("No categories to edit yet.")
    
    with st.expander("📝 Uncategorized Transactions", expanded=len(uncategorized) <= 10):
        # Create a mapping form
        available_categories = get_categories()
        available_categories = [c for c in available_categories if c != "Uncategorized"]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Transaction Details**")
        with col2:
            st.write("**Map to Category**")
        
        st.divider()
        
        # Track mappings
        mappings_made = False
        
        for trans in uncategorized:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                trans_date = pd.to_datetime(trans['date']).strftime('%Y-%m-%d')
                st.write(f"**{trans_date}** · {trans['description'][:60]} · ₱{trans['amount']:.2f}")
            
            with col2:
                new_category = st.selectbox(
                    "Category",
                    options=available_categories,
                    key=f"map_{trans['id']}"
                )
                
                if st.button("✅ Map", key=f"btn_map_{trans['id']}", width="stretch"):
                    # Update the transaction in the database
                    update_transaction_category(trans['id'], new_category)
                    st.success(f"✅ Mapped to {new_category}")
                    mappings_made = True
                    st.rerun()
        
        if mappings_made:
            st.rerun()
    
    # Merchant mapping management
    with st.expander("🏪 Merchant Auto-Categorization Rules", expanded=False):
        st.markdown("Learn from your manual categorizations. Set merchant patterns that will auto-categorize future transactions.")
        
        # Add new merchant mapping
        st.write("**➕ Add New Merchant Pattern**")
        col1, col2, col3 = st.columns([2, 1.5, 1])
        
        with col1:
            merchant_pattern = st.text_input(
                "Merchant Pattern",
                placeholder="e.g., CEBU AIR, NETFLIX, MERALCO",
                help="Enter the merchant name or pattern to match (case-insensitive)",
                key="new_merchant_pattern"
            )
        
        with col2:
            merchant_category = st.selectbox(
                "Category",
                options=get_categories(),
                key="new_merchant_category"
            )
        
        with col3:
            st.write("")  # Spacing
            if st.button("➕ Add Rule", width="stretch"):
                if merchant_pattern and merchant_pattern.strip():
                    add_merchant_mapping(merchant_pattern.strip(), merchant_category)
                    st.success(f"✅ Rule added: {merchant_pattern} → {merchant_category}")
                    st.rerun()
                else:
                    st.error("Please enter a merchant pattern")
        
        st.divider()
        
        # Display existing merchant mappings
        st.write("**📋 Existing Rules**")
        mappings = get_merchant_mappings()
        
        if mappings:
            for mapping in mappings:
                col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 0.5])
                
                with col1:
                    st.write(f"**{mapping['merchant_pattern']}**")
                
                with col2:
                    st.write(mapping['category'])
                
                with col3:
                    st.caption(f"Last used: {mapping['last_used'][:10] if mapping['last_used'] else 'Never'}")
                
                with col4:
                    if st.button("🗑️", key=f"del_merchant_{mapping['id']}", width="stretch"):
                        delete_merchant_mapping(mapping['merchant_pattern'])
                        st.success("✅ Rule deleted")
                        st.rerun()
        else:
            st.info("No merchant rules set yet. Add one to auto-categorize transactions!")
    
    st.divider()

if not transactions:
    st.info("📭 No transactions found for the selected filters. Try adjusting your filters or add some expenses!")
    st.stop()

# Convert to DataFrame
df = pd.DataFrame(transactions)
df['date'] = pd.to_datetime(df['date'])
df['month'] = df['date'].dt.to_period('M').astype(str)

# Key Metrics
st.subheader("💰 Key Metrics")

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

# Visualizations
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
    
    fig_category.update_layout(
        showlegend=True,
        height=400
    )
    
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
        height=400,
        xaxis_title="Account Type",
        yaxis_title="Amount (₱)"
    )
    
    st.plotly_chart(fig_account, width="stretch")

# Monthly trend
st.subheader("📅 Monthly Spending Trend")

monthly_spending = df.groupby('month')['amount'].sum().reset_index()
monthly_spending.columns = ['Month', 'Amount']

fig_trend = px.line(
    monthly_spending,
    x='Month',
    y='Amount',
    title="",
    markers=True
)

fig_trend.update_traces(
    line_color='#1f77b4',
    line_width=3,
    marker_size=10,
    hovertemplate='<b>%{x}</b><br>₱%{y:,.2f}<extra></extra>'
)

fig_trend.update_layout(
    height=400,
    xaxis_title="Month",
    yaxis_title="Amount (₱)",
    hovermode='x unified'
)

st.plotly_chart(fig_trend, width="stretch")

# Top expenses
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("🔝 Top 10 Expenses")
    
    top_expenses = df.nlargest(10, 'amount')[['date', 'description', 'category', 'amount']]
    top_expenses['date'] = top_expenses['date'].dt.strftime('%Y-%m-%d')
    top_expenses['amount'] = top_expenses['amount'].apply(lambda x: f"₱{x:,.2f}")
    top_expenses.columns = ['Date', 'Description', 'Category', 'Amount']
    
    st.dataframe(top_expenses, width="stretch", hide_index=True)

with col2:
    st.subheader("📊 Category Breakdown")
    
    category_breakdown = df.groupby('category').agg({
        'amount': ['sum', 'count', 'mean']
    }).round(2)
    
    category_breakdown.columns = ['Total', 'Count', 'Average']
    category_breakdown = category_breakdown.sort_values('Total', ascending=False)
    category_breakdown['Total'] = category_breakdown['Total'].apply(lambda x: f"₱{x:,.2f}")
    category_breakdown['Average'] = category_breakdown['Average'].apply(lambda x: f"₱{x:,.2f}")
    
    st.dataframe(category_breakdown, width="stretch")

# Recent transactions
st.divider()

st.subheader("📋 Bulk Update Similar Transactions")

# New bulk categorization section
bulk_col1, bulk_col2, bulk_col3 = st.columns([2, 1.5, 1])

with bulk_col1:
    search_merchant = st.text_input(
        "🔍 Find similar transactions",
        placeholder="Type a merchant name (e.g., NETFLIX, BOULDERING, STARBUCKS)...",
        help="Enter merchant name to find and bulk-update similar transactions"
    )

with bulk_col2:
    bulk_threshold = st.slider("Match threshold", 0.5, 1.0, 0.75, 0.05, help="Minimum similarity score")

with bulk_col3:
    st.write("")  # Spacing

if search_merchant and search_merchant.strip():
    # Find similar transactions
    similar_trans = find_similar_transactions(
        search_merchant,
        exclude_id=None,
        similarity_threshold=bulk_threshold
    )
    
    if similar_trans:
        st.info(f"Found {len(similar_trans)} similar transaction(s)")
        
        # Group by category to show current state
        category_groups = {}
        for trans in similar_trans:
            cat = trans['category']
            if cat not in category_groups:
                category_groups[cat] = []
            category_groups[cat].append(trans)
        
        st.write("**Current categories:**")
        for cat, trans_list in sorted(category_groups.items()):
            st.caption(f"  **{cat}**: {len(trans_list)} transaction(s)")
        
        # New category selector
        new_bulk_category = st.selectbox(
            "Change all to:",
            options=get_categories(),
            key="bulk_category_selector"
        )
        
        # Display transactions
        st.write("**Select which ones to update:**")
        
        # Initialize checkbox states
        for trans in similar_trans:
            checkbox_key = f"bulk_trans_{trans['id']}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = False
        
        # Display with checkboxes
        for trans in similar_trans:
            col_check, col_info, col_amount = st.columns([0.3, 2.4, 0.8])
            checkbox_key = f"bulk_trans_{trans['id']}"
            
            with col_check:
                st.checkbox(
                    "Select",
                    value=st.session_state.get(checkbox_key, False),
                    key=checkbox_key,
                    label_visibility="collapsed"
                )
            
            with col_info:
                st.caption(f"{trans['date'][:10]} · {trans['description'][:50]} (Match: {int(trans['similarity_score']*100)}%)")
            
            with col_amount:
                st.caption(f"₱{trans['amount']:.2f}")
        
        # Count selected
        selected_bulk = [
            trans['id'] for trans in similar_trans 
            if st.session_state.get(f"bulk_trans_{trans['id']}", False)
        ]
        
        # Action buttons
        col_action1, col_action2, col_action3 = st.columns(3)
        
        with col_action1:
            if st.button(f"📦 Update Selected ({len(selected_bulk)})", width="stretch", key="bulk_update_selected"):
                if len(selected_bulk) == 0:
                    st.warning("Please select at least one transaction")
                else:
                    update_count = 0
                    for trans_id in selected_bulk:
                        if update_transaction_category(trans_id, new_bulk_category):
                            update_count += 1
                    
                    # Clear checkboxes and mark for refresh
                    for trans in similar_trans:
                        st.session_state.pop(f"bulk_trans_{trans['id']}", None)
                    st.session_state.trans_page = 0
                    st.session_state.data_refresh_key += 1
                    
                    st.success(f"✅ Updated {update_count} transaction(s) to {new_bulk_category}")
                    st.rerun()
        
        with col_action2:
            if st.button(f"⚡ Update All {len(similar_trans)}", width="stretch", key="bulk_update_all"):
                update_count = 0
                for trans in similar_trans:
                    if update_transaction_category(trans['id'], new_bulk_category):
                        update_count += 1
                
                # Clear checkboxes and mark for refresh
                for trans in similar_trans:
                    st.session_state.pop(f"bulk_trans_{trans['id']}", None)
                st.session_state.trans_page = 0
                st.session_state.data_refresh_key += 1
                
                st.success(f"✅ Updated all {update_count} transaction(s) to {new_bulk_category}")
                st.rerun()
        
        with col_action3:
            if st.button("❌ Clear", width="stretch", key="bulk_clear"):
                for trans in similar_trans:
                    st.session_state.pop(f"bulk_trans_{trans['id']}", None)
                st.rerun()
    else:
        st.info(f"No transactions found matching '{search_merchant}'")

st.divider()

st.subheader("📋 Edit All Transactions")

# Search and filter for transactions
search_col, display_col = st.columns([2, 1])

with search_col:
    search_term = st.text_input(
        "🔍 Search transactions",
        placeholder="Search by description, category, account, or amount...",
        help="Type to filter transactions"
    )

with display_col:
    rows_per_page = st.selectbox(
        "Per Page",
        options=[10, 20, 50, 100],
        index=1,
        help="Number of transactions per page"
    )

# Filter transactions based on search
all_trans_df = df.sort_values('date', ascending=False).reset_index(drop=True)

if search_term:
    # Search in description, category, and account
    mask = (
        all_trans_df['description'].str.contains(search_term, case=False, na=False) |
        all_trans_df['category'].str.contains(search_term, case=False, na=False) |
        all_trans_df['account'].str.contains(search_term, case=False, na=False) |
        all_trans_df['amount'].astype(str).str.contains(search_term, case=False, na=False)
    )
    filtered_df = all_trans_df[mask].reset_index(drop=True)
else:
    filtered_df = all_trans_df.reset_index(drop=True)

# Initialize pagination state
if 'trans_page' not in st.session_state:
    st.session_state.trans_page = 0

# Calculate pagination
total_records = len(filtered_df)
total_pages = max(1, (total_records + rows_per_page - 1) // rows_per_page)

# Reset page if out of range
if st.session_state.trans_page >= total_pages:
    st.session_state.trans_page = 0

# Get current page data
start_idx = st.session_state.trans_page * rows_per_page
end_idx = start_idx + rows_per_page
display_df = filtered_df.iloc[start_idx:end_idx]

# Show info
info_col1, info_col2 = st.columns([2, 1])
with info_col1:
    st.write(f"**Showing {start_idx + 1}-{min(end_idx, total_records)} of {total_records} transaction(s)**")
with info_col2:
    st.write(f"**Page {st.session_state.trans_page + 1} of {total_pages}**")

if len(display_df) == 0:
    st.info("No transactions found matching your search.")
else:
    available_categories = [c for c in get_categories() if c != "Uncategorized"]
    
    # Create columns for header
    col1, col2, col3, col4, col5, col6 = st.columns([1.2, 2.5, 1.5, 1, 1.2, 0.8])
    
    with col1:
        st.write("**Date**")
    with col2:
        st.write("**Description**")
    with col3:
        st.write("**Category**")
    with col4:
        st.write("**Amount**")
    with col5:
        st.write("**Account**")
    with col6:
        st.write("**Source**")
    
    st.divider()
    
    # Display transactions with editable categories
    for idx, row in display_df.iterrows():
        col1, col2, col3, col4, col5, col6 = st.columns([1.2, 2.5, 1.5, 1, 1.2, 0.8])
        
        with col1:
            st.write(pd.to_datetime(row['date']).strftime('%Y-%m-%d'))
        
        with col2:
            st.write(row['description'][:40])
        
        with col3:
            # Editable category dropdown
            trans_id = row['id']
            # Include refresh key in widget key to force regeneration on data updates
            new_category = st.selectbox(
                "Category",
                options=available_categories,
                index=available_categories.index(row['category']) if row['category'] in available_categories else 0,
                key=f"trans_cat_{trans_id}_{st.session_state.data_refresh_key}",
                label_visibility="collapsed"
            )
            
            # Update immediately if changed
            if new_category != row['category']:
                update_transaction_category(trans_id, new_category)
                st.session_state.data_refresh_key += 1
                st.rerun()
        
        with col4:
            st.write(f"₱{row['amount']:.2f}")
        
        with col5:
            st.write(row['account'])
        
        with col6:
            st.write(row['source'])
    
    # Pagination controls
    st.divider()
    
    pag_col1, pag_col2, pag_col3, pag_col4, pag_col5 = st.columns([1, 1, 1, 1, 1])
    
    with pag_col1:
        if st.button("⬅️ Previous", width="stretch", disabled=(st.session_state.trans_page == 0)):
            st.session_state.trans_page -= 1
            st.rerun()
    
    with pag_col2:
        st.write("")  # Spacing
    
    with pag_col3:
        # Page selector
        new_page = st.number_input(
            "Go to page",
            min_value=1,
            max_value=total_pages,
            value=st.session_state.trans_page + 1,
            step=1,
            label_visibility="collapsed"
        )
        if new_page != st.session_state.trans_page + 1:
            st.session_state.trans_page = new_page - 1
            st.rerun()
    
    with pag_col4:
        st.write("")  # Spacing
    
    with pag_col5:
        if st.button("Next ➡️", width="stretch", disabled=(st.session_state.trans_page >= total_pages - 1)):
            st.session_state.trans_page += 1
            st.rerun()

# Export option
st.divider()

st.subheader("💾 Export Data")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("Download your filtered transactions as a CSV file for further analysis.")

with col2:
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"expenses_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        width="stretch"
    )
