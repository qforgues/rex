# Statement Processor - Streamlit Web App

A simple, clean web interface for uploading, organizing, and processing your financial statements.

## Features

✅ **Account Management**
- Create, edit, and delete accounts in the sidebar settings
- Organize accounts by holder (you, wife, joint, business)
- Track account details (institution, type, folder, frequency)

✅ **Upload & Process**
- Upload multiple statements at once (PDF, CSV, Excel, images)
- Auto-detect institution and statement date from filename
- Assign files to accounts with dropdown selector
- Files automatically move to account folders

✅ **Data Extraction & Logging**
- Extracts key data from statements
- Maintains `extracted_data.csv` log
- Tracks processing history

## Quick Start

### 1. Install Dependencies

```bash
# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 2. Set Up Your Accounts

Before you can process files, you need to link the app to your `accounts.json` file:

```bash
# Copy your accounts.json to the statement-processor folder
cp ../Financial\ Statements/accounts.json .
```

### 3. Run the App

```bash
streamlit run app.py
```

Streamlit will open automatically in your browser at `http://localhost:8501`

## How to Use

### Step 1: Create/View Accounts (Sidebar)
1. Open the sidebar settings
2. Click **"View Accounts"** to see your accounts
3. Click **"Add Account"** to create a new account
4. Provide:
   - Account name (e.g., "Chase Checking")
   - Institution (e.g., "Chase")
   - Account type (bank, credit_card, investment, loan)
   - Holder (you, wife, joint, business_you, business_wife)
   - Folder path (where statements will be stored)

### Step 2: Upload Statements (Main Area)
1. Click **"Choose statement files"**
2. Select one or more PDF/CSV/Excel files
3. For each file, select the account it belongs to
4. The app will auto-detect the institution and date if your filename includes them

### Step 3: Process Files
1. Review your selections
2. Click **"🚀 Process All Files"**
3. Files are automatically moved to their account folders
4. Data is logged to `extracted_data.csv`

### Step 4: View Results
1. Check the processing results summary
2. View the `extracted_data.csv` log to see all processed statements

## File Naming Tips

For best auto-detection, use filenames like:

```
Chase_Statement_2026-03-15.pdf
Amex_Mar2026.csv
WellsFargo_Checking_2026-03-15.xlsx
```

The app will:
- 🔍 Detect institution: Chase, Amex, Wells Fargo, etc.
- 📅 Extract date: Any YYYY-MM-DD format

## Where Files Go

Files are organized based on your `accounts.json` folder paths:

```
Financial Statements/
├── Personal/
│   ├── Banks/
│   │   └── Chase_Statement_2026-03-15.pdf
│   ├── Credit Cards/
│   │   └── Amex_Statement_2026-03-15.pdf
│   └── Investments/
├── Joint (Me & Wife)/
│   └── Banks/
│   └── Credit Cards/
└── Business (Your Name)/
    ├── Bank Accounts/
    └── Credit Cards/
```

## Logging & Data Extraction

Every time you process files, the app:
1. Reads the statement file (PDF/CSV/Excel)
2. Extracts metadata (date, institution, size)
3. Records entry to `extracted_data.csv`
4. Moves the file to its account folder

View `extracted_data.csv` to see:
- Processing date
- Which account
- Source file
- Extraction timestamp

## Troubleshooting

**"No accounts yet"**
- Create an account first in the sidebar settings

**"Files not appearing in folder"**
- Check the account's `folder_path` in settings
- Ensure the folder exists on your system
- Check if you have write permissions

**"PDF text not extracting"**
- Some PDFs are image-based scans (not OCR'd)
- The app can still move them to the correct folder
- Manual extraction may be needed for these

**"Port 8501 already in use"**
```bash
streamlit run app.py --server.port 8502
```

## Stopping the App

Press `Ctrl+C` in the terminal to stop Streamlit.

## Next Steps

- [ ] Update `accounts.json` with your real account details
- [ ] Download statements from your banks
- [ ] Upload and process your first batch of statements
- [ ] Monitor `extracted_data.csv` for your statement history

---

**Questions?** Refer back to the Financial Statements folder README for more context about the folder structure.
