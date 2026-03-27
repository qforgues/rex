# Setup Guide - Statement Processor

## Prerequisites

You need Python 3.7 or later installed. Check by running:

```bash
python3 --version
```

Don't have Python? Download from [python.org](https://www.python.org/downloads)

---

## Installation Steps

### Step 1: Copy Your Accounts File

First, copy your `accounts.json` from the Financial Statements folder:

**macOS/Linux:**
```bash
cp ../Financial\ Statements/accounts.json .
```

**Windows:**
```bash
copy "..\Financial Statements\accounts.json" .
```

### Step 2: Create Virtual Environment

This isolates the app's dependencies from your system Python.

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```bash
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
```

You should see `(venv)` at the start of your terminal line when activated.

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- Streamlit (web framework)
- Pandas (data processing)
- PyPDF2 (PDF reading)
- OpenPyxl (Excel handling)

---

## Running the App

**macOS/Linux:**
```bash
source venv/bin/activate
streamlit run app.py
```

**Windows (Command Prompt):**
```bash
venv\Scripts\activate
streamlit run app.py
```

**Windows (PowerShell):**
```bash
.\venv\Scripts\Activate.ps1
streamlit run app.py
```

Streamlit will automatically open `http://localhost:8501` in your browser.

---

## Using the App

### First Time Setup

1. **⚙️ Sidebar Settings** → **Add Account**
2. Fill in your account details:
   - Name: "Chase Checking"
   - Institution: "Chase"
   - Type: "bank"
   - Holder: "you"
   - Folder: "Personal/Banks/Chase Checking"

3. Click **Create Account**

### Uploading Statements

1. **Main Area** → **Choose statement files**
2. Select your PDF/CSV/Excel files
3. For each file, select which account it belongs to
4. Click **🚀 Process All Files**

### Viewing Results

- Check the processing summary
- View `extracted_data.csv` to see your history
- Files are automatically organized into your account folders

---

## Deactivating Virtual Environment

When you're done using the app:

```bash
deactivate
```

---

## Restarting Later

To use the app again next time:

**macOS/Linux:**
```bash
source venv/bin/activate
streamlit run app.py
```

**Windows:**
```bash
venv\Scripts\activate
streamlit run app.py
```

---

## Troubleshooting

### "streamlit command not found"
- Make sure your virtual environment is activated
- You should see `(venv)` in your terminal
- Run: `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\activate` (Windows)

### "ModuleNotFoundError"
- Virtual environment not activated
- Or dependencies not installed: `pip install -r requirements.txt`

### "Port 8501 already in use"
Use a different port:
```bash
streamlit run app.py --server.port 8502
```

### Files not moving to folders
- Check that your `accounts.json` has correct folder paths
- Ensure the folders exist on your system
- Check file permissions (read/write access)

---

## Next Steps

1. ✅ Create accounts in the app
2. 📥 Upload your bank statements
3. 📊 Check `extracted_data.csv` for your processing log
4. 🎉 Start analyzing your financial data!

---

For more details, see `README.md`
