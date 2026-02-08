import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from datetime import date
from utils.database import add_transaction, get_categories
from utils.categorizer import suggest_category, get_or_create_category

# Page configuration
st.set_page_config(
    page_title="Add Expense",
    page_icon="✍️",
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

# Main content
st.title("✍️ Add Expense")

st.markdown("Manually add a new expense transaction.")

# Get existing categories
existing_categories = get_categories()
if not existing_categories:
    existing_categories = ["Uncategorized"]

# Expense entry form
with st.form("expense_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        expense_date = st.date_input(
            "Date",
            value=date.today(),
            help="Transaction date"
        )
        
        description = st.text_input(
            "Description",
            placeholder="e.g., Lunch at Jollibee",
            help="What was this expense for?"
        )
        
        amount = st.number_input(
            "Amount (₱)",
            min_value=0.01,
            step=0.01,
            format="%.2f",
            help="Transaction amount in Philippine Pesos"
        )
    
    with col2:
        account = st.selectbox(
            "Account",
            options=["Cash", "Bank", "Credit Card"],
            help="Payment method used"
        )
        
        # Smart category suggestion
        suggested_category = None
        suggested_confidence = 0
        
        if description:
            suggested_category, suggested_confidence = suggest_category(description, existing_categories)
            
            if suggested_confidence >= 60:
                st.info(f"💡 Suggested category: **{suggested_category}** ({suggested_confidence:.0f}% confidence)")
        
        # Category selection with option to add new
        category_options = existing_categories + ["+ Add New Category"]
        
        default_index = 0
        if suggested_category and suggested_category in existing_categories:
            default_index = existing_categories.index(suggested_category)
        
        category_choice = st.selectbox(
            "Category",
            options=category_options,
            index=default_index,
            help="Expense category"
        )
        
        # If user wants to add new category
        new_category = None
        if category_choice == "+ Add New Category":
            new_category = st.text_input(
                "New Category Name",
                placeholder="e.g., Groceries",
                help="Enter a name for the new category"
            )
    
    # Submit button
    submitted = st.form_submit_button("💾 Add Expense", use_container_width=True, type="primary")
    
    if submitted:
        # Validation
        if not description:
            st.error("Please enter a description")
        elif amount <= 0:
            st.error("Amount must be greater than 0")
        elif category_choice == "+ Add New Category" and not new_category:
            st.error("Please enter a category name")
        else:
            # Determine final category
            if category_choice == "+ Add New Category":
                final_category = get_or_create_category(new_category)
                st.success(f"✨ Created new category: **{final_category}**")
            else:
                final_category = category_choice
            
            # Add transaction
            try:
                transaction_id = add_transaction(
                    date=expense_date.strftime("%Y-%m-%d"),
                    description=description,
                    category=final_category,
                    amount=amount,
                    account=account,
                    source="manual"
                )
                
                st.success(f"✅ Expense added successfully! (ID: {transaction_id})")
                st.balloons()
                
            except Exception as e:
                st.error(f"Error adding expense: {str(e)}")

# Recent transactions
st.divider()

st.subheader("📋 Recent Transactions")

from utils.database import get_transactions
import pandas as pd

recent_transactions = get_transactions()[:10]  # Get last 10

if recent_transactions:
    df = pd.DataFrame(recent_transactions)
    
    # Format for display
    display_df = df[['date', 'description', 'category', 'amount', 'account']].copy()
    display_df['amount'] = display_df['amount'].apply(lambda x: f"₱{x:,.2f}")
    display_df.columns = ['Date', 'Description', 'Category', 'Amount', 'Account']
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("No transactions yet. Add your first expense above!")
