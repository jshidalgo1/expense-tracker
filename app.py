import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from utils.database import init_db

# Page configuration
st.set_page_config(
    page_title="Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
init_db()

# Authentication - Load config from YAML file
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    auto_hash=False
)

# Create login widget
try:
    authenticator.login()
except Exception as e:
    st.error(e)

# Check authentication status from session state
if st.session_state.get('authentication_status') is None: # Changed condition to `is None` for initial state
    st.warning("Please enter your username and password")
    st.stop()

# The new API stores authentication status in st.session_state
# We need to retrieve these values from st.session_state
name = st.session_state['name']
authentication_status = st.session_state['authentication_status']
username = st.session_state['username']

if authentication_status == False:
    st.error("Username/password is incorrect")
    st.stop()

if authentication_status == None:
    st.warning("Please enter your username and password")
    st.stop()

# User is authenticated

# If authenticated, show main content
if authentication_status:
    # Sidebar
    with st.sidebar:
        st.title("💰 Expense Tracker")
        st.write(f"Welcome, **{name}**!")
        
        authenticator.logout("Logout", "sidebar")
        
        st.divider()
        
        st.markdown("""
        ### 📱 Navigation
        Use the sidebar to navigate between pages:
        - **Add Expense**: Manual entry
        - **Upload Statements**: PDF import
        - **Dashboard**: View analytics
        - **Categories**: Manage categories
        """)
    
    # Main page content
    st.title("Welcome to Your Expense Tracker! 💰")
    
    st.markdown("""
    ## Getting Started
    
    This app helps you track your expenses with ease:
    
    ### ✍️ Manual Entry
    Navigate to **Add Expense** to manually log your transactions.
    
    ### 📄 PDF Upload
    Upload your bank statements in **Upload Statements** and let the app automatically extract transactions.
    
    ### 📊 Analytics
    View your spending patterns and insights in the **Dashboard**.
    
    ### 🏷️ Categories
    Manage your expense categories in the **Categories** page.
    
    ---
    
    **Currency**: Philippine Peso (₱)
    
    All your data is stored securely in a local database.
    """)
    
    # Quick stats
    from utils.database import get_transactions
    import pandas as pd
    
    st.divider()
    
    st.subheader("📈 Quick Overview")
    
    transactions = get_transactions()
    
    if transactions:
        df = pd.DataFrame(transactions)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Transactions", len(transactions))
        
        with col2:
            total_amount = df['amount'].sum()
            st.metric("Total Expenses", f"₱{total_amount:,.2f}")
        
        with col3:
            categories = df['category'].nunique()
            st.metric("Categories", categories)
    else:
        st.info("No transactions yet. Start by adding an expense or uploading a statement!")
