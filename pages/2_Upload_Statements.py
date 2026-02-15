import streamlit as st
from utils.auth import get_authenticator
import os
import tempfile
import pandas as pd
from utils.database import add_transaction
from utils.ocr_parser import extract_transactions_from_image
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
st.title("📄 Upload Bank Statements (OCR)")

st.subheader("📤 Upload Configuration")

col1, col2 = st.columns(2)

with col1:
    # Bank selection
    # Only show banks we have specific parsers for
    bank_options = ["BPI", "UnionBank"]
    bank_choice = st.selectbox(
        "Bank",
        options=bank_options,
        help="Select your bank to apply the correct OCR parsing logic"
    )
    
    # Account type
    account = st.selectbox(
        "Account Type",
        options=["Credit Card", "Bank", "Cash"],
        help="Type of account for these transactions"
    )

with col2:
    st.info("ℹ️ Upload screenshots of your statement transactions. Ensure the text is clear and readable.")

# File uploader
uploaded_files = st.file_uploader(
    "Upload Statement Images (Screenshots)",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
    help="Upload screenshots of your bank statement transactions"
)

if st.button("🔄 Process Images", width="stretch", type="primary"):
    # Validation
    if not uploaded_files:
        st.error("Please upload at least one image file")
    else:
        # Reset preview state for new submission
        st.session_state.preview_data = []
        st.session_state.editing_rows = {}
        st.session_state.source_images = [] # Store images for preview
        
        # Step 1: Extract all transactions from all files
        st.info(f"📊 Extracting transactions for {bank_choice}...")
        all_extracted_transactions = []
        extraction_errors = []
        
        for uploaded_file in uploaded_files:
            temp_path = None
            try:
                # Save uploaded file temporarily
                suffix = "." + uploaded_file.name.split(".")[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                    file_bytes = uploaded_file.getbuffer()
                    temp_file.write(file_bytes)
                    temp_path = temp_file.name
                    
                    # Store bytes for preview
                    st.session_state.source_images.append({
                        "name": uploaded_file.name,
                        "bytes": bytes(file_bytes)
                    })

                # Extract transactions using OCR
                success, transactions, error = extract_transactions_from_image(temp_path, bank_name=bank_choice)
                
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

# Display preview if we have data in session state
if 'preview_data' in st.session_state and st.session_state.preview_data:
    # Source Images Preview
    if 'source_images' in st.session_state and st.session_state.source_images:
        with st.expander("📸 View Source Screenshots", expanded=False):
            img_cols = st.columns(min(3, len(st.session_state.source_images))) if len(st.session_state.source_images) > 0 else [st]
            for idx, img in enumerate(st.session_state.source_images):
                with img_cols[idx % 3]:
                    st.image(img['bytes'], caption=img['name'], use_container_width=True)

    # Step 2: Preview all transactions with edit/delete options
    st.divider()
    st.subheader("👀 Preview & Edit Transactions")
    
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
                        source="statement_ocr"
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
