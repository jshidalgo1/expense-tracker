import streamlit as st
from utils.auth import get_authenticator
from utils.database import (
    get_categories, add_category, update_category,
    delete_category, get_transactions
)

# Page configuration
st.set_page_config(
    page_title="Categories",
    page_icon="🏷️",
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

# Main content
st.title("🏷️ Manage Categories")

st.markdown("Create, edit, and organize your expense categories.")

# Add new category
st.subheader("➕ Add New Category")

with st.form("add_category_form"):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_category_name = st.text_input(
            "Category Name",
            placeholder="e.g., Groceries, Entertainment",
            help="Enter a unique category name"
        )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        add_submitted = st.form_submit_button("➕ Add Category", width="stretch", type="primary")
    
    if add_submitted:
        if not new_category_name:
            st.error("Please enter a category name")
        else:
            success = add_category(new_category_name)
            if success:
                st.success(f"✅ Category '{new_category_name}' added successfully!")
                st.rerun()
            else:
                st.error(f"❌ Category '{new_category_name}' already exists")

st.divider()

# Existing categories
st.subheader("📋 Existing Categories")

categories = get_categories()

if not categories:
    st.info("No categories yet. Add your first category above!")
else:
    # Get transaction counts for each category
    all_transactions = get_transactions()
    
    category_usage = {}
    for trans in all_transactions:
        cat = trans['category']
        category_usage[cat] = category_usage.get(cat, 0) + 1
    
    # Display categories
    for category in sorted(categories):
        usage_count = category_usage.get(category, 0)
        
        with st.expander(f"🏷️ {category} ({usage_count} transaction{'s' if usage_count != 1 else ''})"):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                # Edit category
                new_name = st.text_input(
                    "Rename to:",
                    value=category,
                    key=f"edit_{category}",
                    help="Enter new name for this category"
                )
                
                if new_name != category:
                    if st.button("💾 Save", key=f"save_{category}"):
                        success = update_category(category, new_name)
                        if success:
                            st.success(f"✅ Renamed to '{new_name}'")
                            st.rerun()
                        else:
                            st.error(f"❌ Category '{new_name}' already exists")
            
            with col2:
                st.metric("Transactions", usage_count)
            
            with col3:
                st.write("")  # Spacing
                if st.button("🗑️ Delete", key=f"delete_{category}", type="secondary"):
                    success, message = delete_category(category)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

# Category statistics
st.divider()

st.subheader("📊 Category Statistics")

if categories and all_transactions:
    import pandas as pd
    
    df = pd.DataFrame(all_transactions)
    
    category_stats = df.groupby('category').agg({
        'amount': ['sum', 'count', 'mean']
    }).round(2)
    
    category_stats.columns = ['Total Spent', 'Transaction Count', 'Average Amount']
    category_stats = category_stats.sort_values('Total Spent', ascending=False)
    
    # Format currency
    category_stats['Total Spent'] = category_stats['Total Spent'].apply(lambda x: f"₱{x:,.2f}")
    category_stats['Average Amount'] = category_stats['Average Amount'].apply(lambda x: f"₱{x:,.2f}")
    
    st.dataframe(category_stats, width="stretch")
else:
    st.info("No transaction data available yet.")

# Tips
st.divider()

st.markdown("""
### 💡 Category Management Tips

1. **Keep it Simple**: Start with broad categories and refine as needed
2. **Merge Similar**: If you have similar categories (e.g., "Food" and "Dining"), rename one to match the other
3. **Can't Delete?**: Categories with existing transactions cannot be deleted. Rename them instead or keep them for historical data
4. **Auto-Created**: Categories from PDF uploads are created automatically based on merchant names
5. **Review Regularly**: Check this page after uploading statements to merge auto-created categories

### 🎯 Suggested Categories

Here are some common expense categories you might want to create:

- **Food & Dining** - Restaurants, groceries, food delivery
- **Transportation** - Gas, public transport, ride-sharing
- **Shopping** - Clothing, electronics, general purchases
- **Utilities** - Electric, water, internet, phone bills
- **Entertainment** - Movies, streaming, hobbies
- **Healthcare** - Medical, dental, pharmacy
- **Bills & Fees** - Credit card fees, subscriptions, insurance
- **Education** - Courses, books, training
- **Personal Care** - Salon, gym, wellness
- **Travel** - Hotels, flights, vacation expenses
""")
