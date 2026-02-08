import streamlit as st
import streamlit_authenticator as stauth
import yaml
import pandas as pd
from yaml.loader import SafeLoader
from utils.database import (
    get_merchant_mappings, add_merchant_mapping,
    delete_merchant_mapping, get_merchant_mapping_stats,
    get_categories, get_transactions, update_transaction_category,
    update_category
)
from utils.merchant_learner import (
    suggest_merchant_mappings, auto_apply_merchant_mappings,
    get_learning_stats
)
from utils.pdf_parser import find_similar_transactions
from utils.categorizer import get_or_create_category

# Page configuration
st.set_page_config(
    page_title="Merchant Rules",
    page_icon="🏪",
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
st.title("🏪 Merchant Auto-Categorization Rules")

st.markdown("""
This page helps you manage automatic merchant-to-category mappings. 
Learn from your transaction history to create rules that automatically categorize future expenses.
""")

# Learning Statistics
st.subheader("📊 Learning Progress")

stats = get_learning_stats()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Transactions", stats['total_transactions'])

with col2:
    st.metric("Merchant Rules", stats['merchant_mappings'])

with col3:
    st.metric("Pending Suggestions", stats['pending_suggestions'])

with col4:
    st.metric("Rule Coverage", f"{stats['coverage_percentage']:.1f}%")

st.divider()

# Suggested New Mappings
st.subheader("💡 Suggested New Merchant Rules")

suggestions = suggest_merchant_mappings(min_frequency=2, confidence_threshold=0.75)

if suggestions:
    st.info(f"Found {len(suggestions)} merchant(s) ready to be auto-categorized based on your transaction history")
    
    # Initialize session state for editable categories
    if "edited_suggestions" not in st.session_state:
        st.session_state.edited_suggestions = {
            merchant: category for merchant, category, _, _ in suggestions
        }
    
    # Get all available categories for editing
    category_list = get_categories()
    
    # Display editable suggestions using columns
    st.markdown("**Edit categories before applying:**")
    
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    with col1:
        st.write("**Merchant**")
    with col2:
        st.write("**Category** (editable)")
    with col3:
        st.write("**Frequency**")
    with col4:
        st.write("**Confidence**")
    
    st.divider()
    
    # Create editable rows for each suggestion
    for merchant, category, frequency, confidence in suggestions:
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
        
        with col1:
            st.write(merchant)
        
        with col2:
            # Editable category dropdown
            edited_cat = st.selectbox(
                f"Category for {merchant}",
                category_list,
                index=category_list.index(st.session_state.edited_suggestions[merchant]) if st.session_state.edited_suggestions[merchant] in category_list else 0,
                key=f"cat_{merchant}",
                label_visibility="collapsed"
            )
            st.session_state.edited_suggestions[merchant] = edited_cat
        
        with col3:
            st.write(str(frequency))
        
        with col4:
            st.write(f"{confidence*100:.1f}%")
    
    st.divider()
    
    # Apply suggestions with edited categories
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col2:
        if st.button("✅ Apply All Suggestions", width="stretch", type="primary"):
            # Apply edited categories
            added = 0
            failed = 0
            for merchant, edited_category in st.session_state.edited_suggestions.items():
                try:
                    if add_merchant_mapping(merchant, edited_category):
                        added += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
            
            if added > 0:
                st.success(f"✅ Applied {added} new merchant rules!")
                if failed > 0:
                    st.warning(f"⚠️ {failed} rules failed to apply")
                st.rerun()
            else:
                st.warning("No new rules were added")
    
    with col3:
        if st.button("🔄 Refresh", width="stretch"):
            st.session_state.edited_suggestions = {}
            st.rerun()
    
    st.divider()

else:
    st.info("No new merchant patterns found yet. Keep adding transactions to build up suggestions!")

st.divider()

# Manual Rule Creation
st.subheader("➕ Create Custom Merchant Rule")

with st.form("add_rule_form"):
    col1, col2 = st.columns([2, 2])
    
    with col1:
        merchant_pattern = st.text_input(
            "Merchant Pattern",
            placeholder="e.g., MCDONALD'S, JOLLIBEE, STARBUCKS",
            help="Enter a merchant name or pattern. Will be matched against transaction descriptions."
        )
    
    with col2:
        category = st.selectbox(
            "Category",
            get_categories() or ["Food & Dining", "Transportation", "Shopping"]
        )
    
    submitted = st.form_submit_button("➕ Add Rule", width="stretch", type="primary")
    
    if submitted:
        if not merchant_pattern or not category:
            st.error("Please fill in all fields")
        else:
            if add_merchant_mapping(merchant_pattern.strip(), category):
                st.success(f"✅ Rule created: {merchant_pattern.upper()} → {category}")
                st.rerun()
            else:
                st.error(f"Rule for '{merchant_pattern}' already exists")

st.divider()

# Existing Merchant Mappings
st.subheader("📋 Existing Merchant Rules")

mappings = get_merchant_mappings()

if mappings:
    # Get mapping stats
    mapping_stats = get_merchant_mapping_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Active Rules", mapping_stats['total_mappings'])
    with col2:
        if mapping_stats['by_category']:
            most_common = max(mapping_stats['by_category'].items(), key=lambda x: x[1])
            st.metric("Most Common Category", most_common[0], f"{most_common[1]} rules")
    
    # Display all mappings
    df_mappings = pd.DataFrame([
        {
            "Merchant Pattern": m['merchant_pattern'],
            "Category": m['category'],
            "Created": pd.to_datetime(m['created_at']).strftime('%Y-%m-%d %H:%M'),
            "Last Used": pd.to_datetime(m['last_used']).strftime('%Y-%m-%d %H:%M') if m['last_used'] else 'Never'
        }
        for m in mappings
    ])
    
    st.dataframe(df_mappings, width="stretch", hide_index=True)
    
    # Delete a rule
    st.subheader("🗑️ Delete Merchant Rule")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        merchant_to_delete = st.selectbox(
            "Select rule to delete",
            [m['merchant_pattern'] for m in mappings],
            key="delete_merchant"
        )
    
    with col2:
        st.write("")  # Spacing
        if st.button("🗑️ Delete Rule", width="stretch", type="secondary"):
            if delete_merchant_mapping(merchant_to_delete):
                st.success(f"✅ Rule deleted: {merchant_to_delete}")
                st.rerun()
            else:
                st.error("Failed to delete rule")

else:
    st.info("No merchant rules created yet. Create your first rule above!")

st.divider()

# Uncategorized Transactions Section
all_transactions_unfiltered = get_transactions()
uncategorized = [t for t in all_transactions_unfiltered if t.get('category') == 'Uncategorized']

if uncategorized:
    st.subheader("🏷️ Map Uncategorized Transactions")
    st.markdown(f"You have **{len(uncategorized)}** uncategorized transaction(s). Categorize them below.")
    
    # Add new category section
    with st.expander("➕ Add New Category", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            new_cat_name = st.text_input("Category Name", placeholder="e.g., Subscriptions, Rent, Gym", key="new_category_input_mr")
        with col2:
            if st.button("➕ Add Category", width="stretch", key="add_cat_btn_mr"):
                if new_cat_name and new_cat_name.strip():
                    get_or_create_category(new_cat_name.strip())
                    st.success(f"✅ Category '{new_cat_name}' added!")
                    st.rerun()
                else:
                    st.error("❌ Please enter a category name")
    
    with st.expander("📝 Uncategorized Transactions", expanded=len(uncategorized) <= 10):
        available_categories = get_categories()
        available_categories = [c for c in available_categories if c != "Uncategorized"]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**Transaction Details**")
        with col2:
            st.write("**Map to Category**")
        
        st.divider()
        
        for trans in uncategorized:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                trans_date = pd.to_datetime(trans['date']).strftime('%Y-%m-%d')
                st.write(f"**{trans_date}** · {trans['description'][:60]} · ₱{trans['amount']:.2f}")
            
            with col2:
                new_category = st.selectbox(
                    "Category",
                    options=available_categories,
                    key=f"map_uncategorized_{trans['id']}"
                )
                
                if st.button("✅ Map", key=f"btn_map_uncategorized_{trans['id']}", width="stretch"):
                    update_transaction_category(trans['id'], new_category)
                    st.success(f"✅ Mapped to {new_category}")
                    st.rerun()
    
    st.divider()

# Bulk Update Similar Transactions Section
st.subheader("📋 Bulk Update Similar Transactions")

bulk_col1, bulk_col2, bulk_col3 = st.columns([2, 1.5, 1])

with bulk_col1:
    search_merchant = st.text_input(
        "🔍 Find similar transactions",
        placeholder="Type a merchant name (e.g., NETFLIX, STARBUCKS)...",
        help="Enter merchant name to find and bulk-update similar transactions",
        key="search_merchant_mr"
    )

with bulk_col2:
    bulk_threshold = st.slider("Match threshold", 0.5, 1.0, 0.75, 0.05, help="Minimum similarity score", key="threshold_mr")

with bulk_col3:
    st.write("")  # Spacing

if search_merchant and search_merchant.strip():
    similar_trans = find_similar_transactions(
        search_merchant,
        exclude_id=None,
        similarity_threshold=bulk_threshold
    )
    
    if similar_trans:
        st.info(f"Found {len(similar_trans)} similar transaction(s)")
        
        category_groups = {}
        for trans in similar_trans:
            cat = trans['category']
            if cat not in category_groups:
                category_groups[cat] = []
            category_groups[cat].append(trans)
        
        st.write("**Current categories:**")
        for cat, trans_list in sorted(category_groups.items()):
            st.caption(f"  **{cat}**: {len(trans_list)} transaction(s)")
        
        new_bulk_category = st.selectbox(
            "Change all to:",
            options=get_categories(),
            key="bulk_category_selector_mr"
        )
        
        st.write("**Select which ones to update:**")
        
        for trans in similar_trans:
            checkbox_key = f"bulk_trans_mr_{trans['id']}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = False
        
        for trans in similar_trans:
            col_check, col_info, col_amount = st.columns([0.3, 2.4, 0.8])
            checkbox_key = f"bulk_trans_mr_{trans['id']}"
            
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
        
        selected_bulk = [
            trans['id'] for trans in similar_trans 
            if st.session_state.get(f"bulk_trans_mr_{trans['id']}", False)
        ]
        
        col_action1, col_action2, col_action3 = st.columns(3)
        
        with col_action1:
            if st.button(f"📦 Update Selected ({len(selected_bulk)})", width="stretch", key="bulk_update_selected_mr"):
                if len(selected_bulk) == 0:
                    st.warning("Please select at least one transaction")
                else:
                    update_count = 0
                    for trans_id in selected_bulk:
                        if update_transaction_category(trans_id, new_bulk_category):
                            update_count += 1
                    
                    for trans in similar_trans:
                        st.session_state.pop(f"bulk_trans_mr_{trans['id']}", None)
                    
                    st.success(f"✅ Updated {update_count} transaction(s) to {new_bulk_category}")
                    st.rerun()
        
        with col_action2:
            if st.button(f"⚡ Update All {len(similar_trans)}", width="stretch", key="bulk_update_all_mr"):
                update_count = 0
                for trans in similar_trans:
                    if update_transaction_category(trans['id'], new_bulk_category):
                        update_count += 1
                
                for trans in similar_trans:
                    st.session_state.pop(f"bulk_trans_mr_{trans['id']}", None)
                
                st.success(f"✅ Updated all {update_count} transaction(s) to {new_bulk_category}")
                st.rerun()
        
        with col_action3:
            if st.button("❌ Clear", width="stretch", key="bulk_clear_mr"):
                for trans in similar_trans:
                    st.session_state.pop(f"bulk_trans_mr_{trans['id']}", None)
                st.rerun()
    else:
        st.info(f"No transactions found matching '{search_merchant}'")

st.divider()

# Information section
st.subheader("ℹ️ How It Works")

with st.expander("Learn about Merchant Auto-Categorization"):
    st.markdown("""
    ### How Merchant Learning Works
    
    1. **Analysis**: The system analyzes your transaction history to identify patterns
    2. **Pattern Recognition**: Identifies merchants that consistently appear in the same category
    3. **Suggestions**: Creates rules when a merchant appears 3+ times in the same category with 75%+ confidence
    4. **Auto-Categorization**: Applies these rules to future transactions automatically
    
    ### Benefits
    - ⏱️ **Save Time**: Automatically categorize similar transactions
    - 🎯 **Consistency**: Ensure similar merchants are always categorized the same way
    - 🧠 **Learning**: System learns from your categorization patterns
    - 🔄 **Flexibility**: Edit or delete rules anytime
    
    ### Configuration
    - **Minimum Frequency**: A merchant must appear 3+ times to suggest a rule
    - **Confidence Threshold**: 75%+ of transactions must be in the same category
    - **Pattern Matching**: Rules match merchant names in transaction descriptions
    """)

st.divider()

# Auto-learning suggestions
st.subheader("🤖 Auto-Learning Options")

col1, col2 = st.columns(2)

with col1:
    st.info("💡 **Tip**: Review suggested rules regularly to keep your categorization accurate and up-to-date.")

with col2:
    if st.button("🔍 Refresh Suggestions", width="stretch"):
        st.rerun()
