import streamlit as st
import os
import tempfile
from pathlib import Path
from datetime import datetime

import account_manager as am
import file_processor as fp

# Page config
st.set_page_config(
    page_title="Statement Processor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("📊 Financial Statement Processor")
st.markdown("Organize, upload, and process your financial statements")

# Sidebar for settings
with st.sidebar:
    st.header("⚙️ Settings")

    tab = st.radio(
        "Account Management",
        ["View Accounts", "Add Account", "Edit Account", "Delete Account"],
        key="sidebar_tab"
    )

    accounts = am.load_accounts()

    # VIEW ACCOUNTS
    if tab == "View Accounts":
        st.subheader("📋 Your Accounts")

        if not accounts:
            st.info("No accounts yet. Create one to get started!")
        else:
            # Filter by holder
            holders = am.get_holders()
            selected_holder = st.selectbox("Filter by:", ["All"] + holders)

            filtered = accounts if selected_holder == "All" else am.get_accounts_by_holder(selected_holder)

            if filtered:
                for acc in filtered:
                    with st.expander(f"**{acc['account_name']}** ({acc['institution']})"):
                        st.write(f"**Type:** {acc['account_type'].replace('_', ' ').title()}")
                        st.write(f"**Holder:** {acc['holder']}")
                        st.write(f"**Folder:** {acc['folder_path']}")
                        st.write(f"**Last 4:** {acc['account_number_last4']}")
                        st.write(f"**Frequency:** {acc['statement_frequency']}")
                        if acc.get('notes'):
                            st.write(f"**Notes:** {acc['notes']}")
            else:
                st.info("No accounts found for this holder.")

    # ADD ACCOUNT
    elif tab == "Add Account":
        st.subheader("➕ Create New Account")

        with st.form("add_account_form"):
            col1, col2 = st.columns(2)

            with col1:
                account_name = st.text_input("Account Name", placeholder="e.g., Chase Checking")
                institution = st.text_input("Institution", placeholder="e.g., Chase Bank")
                account_type = st.selectbox("Type", ["bank", "credit_card", "investment", "loan"])

            with col2:
                holder = st.selectbox("Holder", ["you", "wife", "joint", "business_you", "business_wife"])
                account_number = st.text_input("Last 4 Digits", placeholder="XXXX", max_chars=4)
                statement_freq = st.selectbox("Statement Frequency", ["monthly", "quarterly", "annual"])

            folder_path = st.text_input("Folder Path", placeholder="e.g., Personal/Banks/Chase")
            notes = st.text_area("Notes", placeholder="Optional notes about this account")

            if st.form_submit_button("Create Account", type="primary"):
                new_account = am.create_account({
                    "account_name": account_name,
                    "institution": institution,
                    "account_type": account_type,
                    "holder": holder,
                    "folder_path": folder_path,
                    "account_number_last4": account_number,
                    "statement_frequency": statement_freq,
                    "notes": notes
                })
                st.success(f"✅ Account '{account_name}' created!")
                st.rerun()

    # EDIT ACCOUNT
    elif tab == "Edit Account":
        st.subheader("✏️ Edit Account")

        if not accounts:
            st.warning("No accounts to edit.")
        else:
            account_options = {acc['account_name']: acc['account_id'] for acc in accounts}
            selected_name = st.selectbox("Select Account:", list(account_options.keys()))
            selected_id = account_options[selected_name]
            selected_account = am.get_account_by_id(selected_id)

            with st.form("edit_account_form"):
                col1, col2 = st.columns(2)

                with col1:
                    new_name = st.text_input("Account Name", value=selected_account['account_name'])
                    new_institution = st.text_input("Institution", value=selected_account['institution'])
                    new_type = st.selectbox("Type", ["bank", "credit_card", "investment", "loan"],
                                           index=["bank", "credit_card", "investment", "loan"].index(selected_account['account_type']))

                with col2:
                    new_holder = st.selectbox("Holder", ["you", "wife", "joint", "business_you", "business_wife"],
                                             index=["you", "wife", "joint", "business_you", "business_wife"].index(selected_account['holder']))
                    new_account_num = st.text_input("Last 4 Digits", value=selected_account['account_number_last4'])
                    new_freq = st.selectbox("Statement Frequency", ["monthly", "quarterly", "annual"],
                                           index=["monthly", "quarterly", "annual"].index(selected_account['statement_frequency']))

                new_folder = st.text_input("Folder Path", value=selected_account['folder_path'])
                new_notes = st.text_area("Notes", value=selected_account.get('notes', ''))

                if st.form_submit_button("Update Account", type="primary"):
                    am.update_account(selected_id, {
                        "account_name": new_name,
                        "institution": new_institution,
                        "account_type": new_type,
                        "holder": new_holder,
                        "account_number_last4": new_account_num,
                        "statement_frequency": new_freq,
                        "folder_path": new_folder,
                        "notes": new_notes
                    })
                    st.success(f"✅ Account updated!")
                    st.rerun()

    # DELETE ACCOUNT
    elif tab == "Delete Account":
        st.subheader("🗑️ Delete Account")

        if not accounts:
            st.warning("No accounts to delete.")
        else:
            account_options = {acc['account_name']: acc['account_id'] for acc in accounts}
            selected_name = st.selectbox("Select Account:", list(account_options.keys()))
            selected_id = account_options[selected_name]

            st.warning(f"⚠️ This will delete '{selected_name}' from the account list (files won't be deleted).")

            if st.button("Delete Account", type="secondary"):
                am.delete_account(selected_id)
                st.success(f"✅ Account deleted!")
                st.rerun()

# Main content area
st.markdown("---")

# UPLOAD & PROCESS SECTION
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📁 Upload Statements")
    st.markdown("Upload one or more statement files (PDF, CSV, Excel)")

with col2:
    st.metric("Total Accounts", len(accounts))

# File uploader
uploaded_files = st.file_uploader(
    "Choose statement files",
    type=["pdf", "csv", "xlsx", "xls", "jpg", "png"],
    accept_multiple_files=True,
    key="file_uploader"
)

if uploaded_files:
    st.subheader("📋 Review & Assign Accounts")

    account_options = {acc['account_name']: acc['account_id'] for acc in accounts}

    if not account_options:
        st.error("❌ Please create at least one account before processing files.")
    else:
        # Create a form for each file
        assignments = {}

        for i, uploaded_file in enumerate(uploaded_files):
            col_file, col_select = st.columns([2, 1])

            with col_file:
                # File info
                st.write(f"**{i+1}. {uploaded_file.name}**")
                st.caption(f"Size: {uploaded_file.size / 1024:.1f} KB")

                # Auto-detect institution
                detected_inst = fp.detect_institution(uploaded_file.name)
                detected_date = fp.extract_date_from_filename(uploaded_file.name)

                if detected_inst:
                    st.caption(f"🔍 Detected: {detected_inst.title()}")
                if detected_date:
                    st.caption(f"📅 Date: {detected_date}")

            with col_select:
                account = st.selectbox(
                    "Account:",
                    list(account_options.keys()),
                    key=f"select_{i}"
                )
                assignments[uploaded_file.name] = account_options[account]

        # Process button
        if st.button("🚀 Process All Files", type="primary"):
            progress_bar = st.progress(0)
            status_placeholder = st.empty()

            results = []

            for i, uploaded_file in enumerate(uploaded_files):
                status_placeholder.info(f"Processing {i+1}/{len(uploaded_files)}: {uploaded_file.name}")

                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                    tmp_file.write(uploaded_file.getbuffer())
                    tmp_path = tmp_file.name

                try:
                    account_id = assignments[uploaded_file.name]
                    selected_account = am.get_account_by_id(account_id)
                    account_folder = selected_account['folder_path']

                    # Process the file
                    result = fp.process_uploaded_file(tmp_path, account_id, account_folder)
                    results.append(result)

                    # Extract data
                    extraction = fp.extract_statement_data(result.get('destination', tmp_path))

                    # Log extraction
                    log_entry = {
                        "date": detected_date or datetime.now().strftime("%Y-%m-%d"),
                        "account": selected_account['account_name'],
                        "account_type": selected_account['account_type'],
                        "institution": selected_account['institution'],
                        "holder": selected_account['holder'],
                        "amount": "TBD",
                        "source_file": uploaded_file.name,
                        "extracted_at": datetime.now().isoformat(),
                        "notes": f"File type: {extraction.get('content_type', 'unknown')}"
                    }
                    fp.save_extraction_log(log_entry, "extracted_data.csv")

                finally:
                    # Clean up temp file
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

                progress_bar.progress((i + 1) / len(uploaded_files))

            status_placeholder.empty()
            progress_bar.empty()

            # Show results
            st.success(f"✅ Processed {len(results)} files!")

            with st.expander("View Processing Results"):
                for result in results:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"📄 **{result['filename']}")
                    with col2:
                        st.write(f"✅ {result['status'].upper()}")
                    with col3:
                        if result.get('extracted_date'):
                            st.write(f"📅 {result['extracted_date']}")

            # Show updated extraction log
            if os.path.exists("extracted_data.csv"):
                import pandas as pd
                log_df = pd.read_csv("extracted_data.csv")
                st.subheader("📊 Extraction Log")
                st.dataframe(log_df, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
**💡 Tips:**
- File names should include dates (YYYY-MM-DD) for automatic date detection
- Institution names in filenames help with auto-detection (Chase, Amex, etc.)
- All files are organized by account folder automatically
- Check `extracted_data.csv` to see your processing history
""")
