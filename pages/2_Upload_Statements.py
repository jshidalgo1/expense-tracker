import streamlit as st
from utils.auth import get_authenticator
import os
import tempfile
import pandas as pd
from utils.database import (
    add_transaction, get_bank_passwords, get_bank_password,
    add_bank_password, delete_bank_password, get_transactions,
)
from utils.database import delete_all_transactions
import time
from utils.pdf_parser import extract_transactions
from utils.categorizer import auto_categorize, get_or_create_category

# Page configuration
st.set_page_config(
    page_title="Upload Statements",
    page_icon="📄",
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
st.title("📄 Upload Bank Statements")

st.markdown("Upload PDF bank statements to automatically extract transactions. PDFs are processed temporarily and not stored.")

# Get saved banks
saved_banks = get_bank_passwords()
bank_names = [bank['bank_name'] for bank in saved_banks]

# Upload form
# Create tabs
tab_upload, tab_manage = st.tabs(["📤 Upload & Add", "🔐 Manage Banks"])

with tab_upload:
    st.subheader("📤 Upload Configuration")

    col1, col2 = st.columns(2)

    with col1:
        # Bank selection
        bank_options = bank_names + ["+ Add New Bank"]
        bank_choice = st.selectbox(
            "Bank",
            options=bank_options,
            help="Select your bank or add a new one"
        )
        
        # If new bank, show input
        new_bank_name = None
        if bank_choice == "+ Add New Bank":
            new_bank_name = st.text_input(
                "Bank Name",
                placeholder="e.g., BPI, UnionBank",
                help="Enter the name of your bank"
            )
        
        # Account type
        account = st.selectbox(
            "Account Type",
            options=["Credit Card", "Bank", "Cash"],
            help="Type of account for these transactions"
        )

    with col2:
        # Password input (auto-fill if bank exists)
        default_password = ""
        if bank_choice != "+ Add New Bank" and bank_choice in bank_names:
            saved_password = get_bank_password(bank_choice)
            if saved_password:
                default_password = saved_password
        
        password = st.text_input(
            "PDF Password",
            value=default_password,
            type="password",
            help="Password to unlock the PDF (if protected)"
        )
        
        # Save password option
        save_password = st.checkbox(
            "💾 Save/Update password for this bank",
            value=False,
            help="Store this password for future uploads"
        )

    # File uploader
    uploaded_files = st.file_uploader(
        "Upload PDF Statements",
        type=["pdf"],
        accept_multiple_files=True,
        help="You can upload multiple PDF files at once"
    )
        
    col_submit, col_save = st.columns([1, 1])
    
    with col_submit:
        submitted = st.button("🔄 Process Statements", width="stretch", type="primary")
        
    with col_save:
        saved_config = st.button("💾 Save Bank Config Only", width="stretch")

    if saved_config or submitted:
        # Determine final bank name
        final_bank_name = new_bank_name if bank_choice == "+ Add New Bank" else bank_choice
        
        # Save password if requested (or if just saving config)
        if (save_password or saved_config) and password and final_bank_name:
            if bank_choice == "+ Add New Bank" and not new_bank_name:
                st.error("Please enter a bank name")
            else:
                add_bank_password(final_bank_name, password)
                st.success(f"✅ Password saved for {final_bank_name}")
                if saved_config:
                    st.rerun()

    if submitted:
        # Validation
        if bank_choice == "+ Add New Bank" and not new_bank_name:
            st.error("Please enter a bank name")
        elif not uploaded_files:
            st.error("Please upload at least one PDF file")
        else:
            # Determine final bank name (re-evaluate for process scope)
            final_bank_name = new_bank_name if bank_choice == "+ Add New Bank" else bank_choice

            # Reset preview state for new submission
            st.session_state.preview_data = []
            st.session_state.editing_rows = {}
            
            # Step 1: Extract all transactions from all files
            st.info("📊 Extracting transactions from files...")
            all_extracted_transactions = []
            extraction_errors = []
            
            for uploaded_file in uploaded_files:
                temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                        temp_file.write(uploaded_file.getbuffer())
                        temp_path = temp_file.name

                    # Extract transactions
                    success, transactions, error = extract_transactions(
                        temp_path,
                        password=password if password else None,
                        bank_type="auto"
                    )
                except Exception as exc:
                    success = False
                    transactions = []
                    error = str(exc)
                finally:
                    if temp_path and os.path.exists(temp_path):
                        os.remove(temp_path)

                if success:
                    all_extracted_transactions.append({
                        'filename': uploaded_file.name,
                        'transactions': transactions
                    })
                else:
                    extraction_errors.append(f"{uploaded_file.name}: {error}")
            
            # Show extraction results
            if extraction_errors:
                for error in extraction_errors:
                    st.error(f"❌ {error}")
            
            # Build preview data for this submission
            if all_extracted_transactions:
                total_transactions = 0
                preview_data = []
                
                for file_data in all_extracted_transactions:
                    st.write(f"**📄 {file_data['filename']}** ({len(file_data['transactions'])} transactions)")
                    
                    for trans in file_data['transactions']:
                        # Auto-categorize
                        category = auto_categorize(trans['description'])
                        if not category:
                            category = "Uncategorized"
                        
                        preview_data.append({
                            'Date': trans['date'],
                            'Description': trans['description'],
                            'Amount': trans['amount'],
                            'Category': category,
                            'Account': account,
                            '_original_data': trans  # Keep original for reference
                        })
                        total_transactions += 1
                
                st.session_state.preview_data = preview_data
                st.session_state.editing_rows = {}
            else:
                if not extraction_errors:
                    st.warning("No transactions were extracted from the uploaded file(s).")
    
    # Display preview if we have data in session state (OUTSIDE the if submitted block)
    if 'preview_data' in st.session_state and st.session_state.preview_data:
        # Step 2: Preview all transactions with edit/delete options
        st.divider()
        st.subheader("👀 Preview & Edit Transactions")
        st.markdown("Review the transactions below. You can remove rows or edit details before saving to the database.")
        
        # Show current transaction count
        st.write(f"**Total Transactions: {len(st.session_state.preview_data)}**")
        
        # Create columns for table header
        col1, col2, col3, col4, col5, col6, col7 = st.columns([1.5, 3, 1.5, 1.5, 1.2, 1.5, 0.8])
        
        with col1:
            st.write("**Date**")
        with col2:
            st.write("**Description**")
        with col3:
            st.write("**Amount**")
        with col4:
            st.write("**Category**")
        with col5:
            st.write("**Account**")
        with col6:
            st.write("**Edit**")
        with col7:
            st.write("**Remove**")
        
        st.divider()
        
        # Track rows to remove after rendering
        rows_to_remove = []
        
        # Display each transaction with edit/delete buttons
        for idx, trans in enumerate(st.session_state.preview_data):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1.5, 3, 1.5, 1.5, 1.2, 1.5, 0.8])
            
            with col1:
                st.write(trans['Date'])
            
            with col2:
                st.write(trans['Description'][:50])
            
            with col3:
                st.write(f"PHP {trans['Amount']:.2f}")
            
            with col4:
                st.write(trans['Category'])
            
            with col5:
                st.write(trans['Account'])
            
            with col6:
                if st.button("✏️ Edit", key=f"edit_{idx}", help="Edit this transaction"):
                    st.session_state.editing_rows[idx] = not st.session_state.editing_rows.get(idx, False)
            
            with col7:
                if st.button("🗑️", key=f"remove_{idx}", help="Remove this transaction"):
                    rows_to_remove.append(idx)
        
        # Remove marked rows (in reverse order to avoid index shifting)
        for idx in sorted(rows_to_remove, reverse=True):
            st.session_state.preview_data.pop(idx)
            if idx in st.session_state.editing_rows:
                del st.session_state.editing_rows[idx]
        
        if rows_to_remove:
            st.rerun()
        
        st.divider()
        
        # Show edit forms after the table
        for idx, trans in enumerate(st.session_state.preview_data):
            if st.session_state.editing_rows.get(idx, False):
                st.divider()
                st.subheader(f"Edit Transaction #{idx + 1}")
                
                edit_col1, edit_col2, edit_col3, edit_col4 = st.columns(4)
                
                with edit_col1:
                    new_date = st.date_input("Date", value=pd.to_datetime(trans['Date']).date(), key=f"date_{idx}")
                
                with edit_col2:
                    new_desc = st.text_input("Description", value=trans['Description'], key=f"desc_{idx}")
                
                with edit_col3:
                    new_amount = st.number_input("Amount", value=trans['Amount'], min_value=0.0, step=0.01, key=f"amount_{idx}")
                
                with edit_col4:
                    from utils.database import get_categories
                    available_categories = get_categories()
                    new_category = st.selectbox("Category", options=available_categories, 
                                               index=available_categories.index(trans['Category']) if trans['Category'] in available_categories else 0,
                                               key=f"cat_{idx}")
                
                edit_btn_col1, edit_btn_col2 = st.columns(2)
                
                with edit_btn_col1:
                    if st.button("✅ Save Changes", key=f"save_{idx}"):
                        st.session_state.preview_data[idx]['Date'] = str(new_date)
                        st.session_state.preview_data[idx]['Description'] = new_desc
                        st.session_state.preview_data[idx]['Amount'] = new_amount
                        st.session_state.preview_data[idx]['Category'] = new_category
                        st.session_state.editing_rows[idx] = False
                        st.rerun()
                
                with edit_btn_col2:
                    if st.button("❌ Cancel", key=f"cancel_{idx}"):
                        st.session_state.editing_rows[idx] = False
                        st.rerun()
                
                st.divider()
        
        st.divider()
        
        # Step 3: Confirm and save
        col_confirm, col_cancel = st.columns(2)
        
        with col_confirm:
            if st.button("✅ Confirm & Save to Database", type="primary", width="stretch"):
                if len(st.session_state.preview_data) == 0:
                    st.error("❌ No transactions to save. Please upload files again.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    new_categories_created = []
                    
                    processed = 0
                    total = len(st.session_state.preview_data)
                    
                    for trans in st.session_state.preview_data:
                        status_text.text(f"Saving: {trans['Description'][:40]}...")
                        
                        # Add transaction with edited values
                        add_transaction(
                            date=trans['Date'],
                            description=trans['Description'],
                            category=trans['Category'],
                            amount=trans['Amount'],
                            account=trans['Account'],
                            source="statement_pdf"
                        )
                        
                        # Track new categories
                        if trans['Category'] not in new_categories_created and trans['Category'] != "Uncategorized":
                            from utils.database import get_categories
                            existing = get_categories()
                            if trans['Category'] not in existing:
                                new_categories_created.append(trans['Category'])
                        
                        processed += 1
                        progress_bar.progress(processed / total)
                    
                    status_text.empty()
                    progress_bar.empty()
                    
                    # Summary
                    st.divider()
                    st.subheader("📊 Processing Summary")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Transactions Saved", total)
                    
                    with col2:
                        if new_categories_created:
                            st.info(f"✨ New categories created: {', '.join(new_categories_created)}")
                    
                    st.success("✅ All transactions have been saved to the database!")
                    st.balloons()
                    
                    # Clear preview data after successful save
                    st.session_state.preview_data = []
        
        with col_cancel:
            st.info("👆 Review the transactions above. Edit or remove rows as needed. Click 'Confirm & Save' to proceed, or upload again to start over.")

with tab_manage:
    st.subheader("🔐 Manage Saved Banks")
    st.markdown("View and manage saved bank passwords for quick PDF processing.")
    
    if saved_banks:
        for bank in saved_banks:
            # Use a container for better spacing
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.markdown(f"**🏦 {bank['bank_name']}**")
                
                with col2:
                    # Show masked password
                    masked = "•" * len(bank['password'])
                    st.text(f"Password: {masked}")
                
                with col3:
                    if st.button("🗑️ Delete", key=f"delete_{bank['bank_name']}", type="secondary", width="stretch"):
                        delete_bank_password(bank['bank_name'])
                        st.rerun()
                st.divider()
    else:
        st.info("No saved bank passwords yet. Add a bank in the 'Upload & Add' tab.")

# Danger Zone (keep outside tabs)
st.divider()
with st.expander("⚠️ Danger Zone"):
    st.warning("These actions are irreversible!")
    
    # Show current count
    count = len(get_transactions())
    st.write(f"Current transactions: **{count}**")
    
    if st.button("🗑️ Clear All Transactions", type="primary", help="Delete ALL transactions from the database"):
        
        delete_all_transactions()
        st.success("✅ All transactions have been deleted.")
        time.sleep(1.5)
        st.rerun()

# Tips
st.divider()

st.markdown("""
### 💡 Tips for Best Results

1. **Password Protection**: Most bank PDFs are password-protected. Enter the password before processing.
2. **Save Passwords**: Check "Save password" to avoid re-entering it for future uploads from the same bank.
3. **Multiple Files**: You can upload multiple statements at once if they use the same password.
4. **Auto-Categorization**: Transactions are automatically categorized based on merchant names.
5. **Review Categories**: Check the Categories page to merge or rename auto-created categories.

### 🔒 Privacy & Security

- Passwords are stored locally in your database
- PDF files are processed temporarily and not stored
- No data is sent to external servers
""")
