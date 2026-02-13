# ... (imports)
import streamlit as st
from utils.auth import get_authenticator
from utils.database import init_db
from utils.profiler import get_profiler_stats, scope_timer

# Page configuration
st.set_page_config(
    page_title="Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clear profiler stats at the start of the run to avoid stale data
if 'profiler_stats' in st.session_state:
    st.session_state['profiler_stats'] = {}

# Initialize database
init_db()

# ... (authentication code remains the same until sidebar)

# Authentication - Load config from Streamlit secrets
authenticator = get_authenticator()

# Create login widget
try:
    authenticator.login()
except Exception as e:
    st.error(e)

# Check authentication status from session state
if st.session_state.get('authentication_status') is None:
    st.warning("Please enter your username and password")
    st.stop()

# The new API stores authentication status in st.session_state
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
        - **Summary**: At-a-glance overview
        - **Add Expense**: Manual entry
        - **Upload Statements**: PDF import
        - **Dashboard**: View analytics
        - **Categories**: Manage categories
        - **Finance Log**: Track overall net worth
        - **Goals**: Monthly budgets and limits
        """)

        st.divider()
        
        # Placeholder for performance stats - will be filled at the end
        stats_container = st.empty()
    
    # Main page content
    st.title("Welcome to Your Expense Tracker! 💰")
    
    st.markdown("""
    ## Getting Started
    
    This app helps you track your expenses with ease:

    ### 🧾 Summary
    Start with **Summary** to see key insights at a glance.
    
    ### ✍️ Manual Entry
    Navigate to **Add Expense** to manually log your transactions.
    
    ### 📄 PDF Upload
    Upload your bank statements in **Upload Statements** and let the app automatically extract transactions.
    
    ### 📊 Analytics
    View your spending patterns and insights in the **Dashboard**.

    ### 💼 Finance Log
    Log total assets and debt each cutoff to see net worth over time.
    
    ### 🎯 Goals
    Set monthly budgets per category and track your progress.

    ### 🏷️ Categories
    Manage your expense categories in the **Categories** page.
    
    ---
    
    **Currency**: Philippine Peso (₱)
    
    All your data is stored securely in a local database.
    """)
    
    # Quick stats
    from utils.database import get_dashboard_stats
    
    st.divider()
    
    st.subheader("📈 Quick Overview")
    
    # Measure the actual call time (including cache hits)
    with scope_timer("Fetch Dashboard Stats (Latency)"):
        stats = get_dashboard_stats()
    
    if stats['count'] > 0:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Transactions", stats['count'])
        
        with col2:
            st.metric("Total Expenses", f"₱{stats['total_amount']:,.2f}")
        
        with col3:
            st.metric("Categories", stats['categories'])
    else:
        st.info("No transactions yet. Start by adding an expense or uploading a statement!")

    # Render performance stats at the end
    with stats_container.container():
        with st.expander("⏱️ Performance Stats"):
            current_stats = get_profiler_stats()
            if current_stats:
                for key, value in current_stats.items():
                    st.write(f"**{key}:** {value:.4f}s")
            else:
                st.write("No profiling data available.")
            
            if st.button("Clear Cache & Rerun"):
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()
