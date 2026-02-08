import streamlit as st
import streamlit_authenticator as stauth
import yaml
import pandas as pd
from yaml.loader import SafeLoader
from utils.database import (
    get_merchant_mappings, add_merchant_mapping,
    delete_merchant_mapping, get_merchant_mapping_stats,
    get_categories
)
from utils.merchant_learner import (
    suggest_merchant_mappings, auto_apply_merchant_mappings,
    get_learning_stats
)

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
