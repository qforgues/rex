# Statement Organizer - Test Environment

Welcome! You have a complete statement management system ready to test.

## 📁 Folder Structure

```
Statements/
├── Personal/
│   ├── Joint/              # Joint accounts (you + Courtney)
│   │   ├── Banks/
│   │   └── Credit_Cards/
│   ├── You/                # Your personal accounts
│   │   ├── Banks/
│   │   └── Credit_Cards/
│   └── Courtney/           # Courtney's personal accounts
│       ├── Banks/
│       └── Credit_Cards/
├── Business-You/           # Your business (Portal42, etc.)
│   ├── Banks/              # ← Dart Bank goes here
│   └── Credit_Cards/
├── Business-Courtney/      # Courtney's business
│   ├── Banks/
│   └── Credit_Cards/
├── Logs/                   # Auto-created, contains all reports
│   ├── statement-processing-*.log
│   ├── freshbooks-sync-*.log
│   └── freshbooks-matches-*.csv
├── .statement-formats.json # Learned format mappings (auto-created)
└── .freshbooks-config.json # Your FreshBooks credentials (create this)
```

## 🎯 Quick Start

### 1. Test with Sample Data

Three sample statements are already included:

| File | Location | Type | Purpose |
|------|----------|------|---------|
| `Banco-Popular-Joint-2026-03.csv` | `Personal/Joint/Banks/` | Bank | Spanish format, 15 transactions |
| `Dart-Bank-2026-03.csv` | `Business-You/Banks/` | Bank | Portal42 payroll, 14 transactions |
| `Chase-Personal-2026-03.csv` | `Personal/You/Credit_Cards/` | Credit | Personal card, 15 transactions |

**To process them:**

```bash
# Option A: Use the Python script directly
python /sessions/amazing-sharp-clarke/mnt/rex/statement-organizer/scripts/process_statement.py

# Option B: Use Claude to process them
# Ask: "Process all my sample statements and show me the logs"
```

### 2. View the Dashboard

Open this in your browser to see an interactive dashboard:

```
/sessions/amazing-sharp-clarke/mnt/rex/statement-dashboard.html
```

The dashboard shows:
- Ready statements and their status
- Quick action buttons
- Folder structure overview
- Getting started instructions

### 3. Check the Logs

After processing, find logs here:

```
/Statements/Logs/
```

**Files you'll see:**

- **statement-processing-2026-03-23.log** - Format detection, parsing results
- **freshbooks-sync-2026-03-23.log** - Invoice matching attempts
- **freshbooks-matches-2026-03-23.csv** - Matched/ambiguous/unmatched transactions

### 4. Add Your Real Statements

1. Download statements from your banks/credit cards as CSV
2. Copy them to the appropriate folders:
   ```
   Banco Popular (Joint)      → Personal/Joint/Banks/
   Banco Popular (You)        → Personal/You/Banks/
   Banco Popular (Courtney)   → Personal/Courtney/Banks/

   Credit Cards (You)         → Personal/You/Credit_Cards/
   Credit Cards (Joint)       → Personal/Joint/Credit_Cards/

   Dart Bank (Portal42)       → Business-You/Banks/
   [Your Credit Cards]        → Business-You/Credit_Cards/

   [Courtney's Business]      → Business-Courtney/Banks/
   ```
3. Process them with the skill

## 🔧 Configuration

### FreshBooks Integration (Optional)

To enable automatic invoice marking, create a config file:

```json
// .freshbooks-config.json
{
  "api_token": "your_freshbooks_api_token_here",
  "account_id": "your_account_id"
}
```

Or set environment variable:

```bash
export FRESHBOOKS_API_TOKEN="your_token_here"
```

### Format Learning

The first time you process a statement type, the skill learns its format and saves it to `.statement-formats.json`. Future statements from the same bank are parsed instantly without re-learning.

## 📊 What Gets Processed

### For All Statements:
- ✓ Format detection (bank/card type)
- ✓ Column identification (date, amount, merchant)
- ✓ Transaction extraction
- ✓ Organization into correct folders
- ✓ Logging of all operations

### For Dart Bank (Business-You/Banks/):
- ✓ FreshBooks invoice matching (amount + dispensary name)
- ✓ Confidence scoring (≥90% auto-mark, 70-89% ambiguous, <70% unmatched)
- ✓ 3-category report (matched, ambiguous, unmatched)
- ✓ API integration for marking invoices paid

### For Credit Cards:
- ✓ Merchant and category parsing
- ✓ Transaction classification
- ✓ Anomaly detection (fraudulent/unusual spending)
- ✓ Severity flagging (HIGH/MEDIUM/LOW)

## 📋 Sample Outputs

### Format Mapping (`.statement-formats.json`)

```json
{
  "Banco Popular": {
    "date_column": "Fecha",
    "amount_column": "Monto",
    "merchant_column": "Descripción",
    "debit_amount_column": "Débito",
    "credit_amount_column": "Crédito",
    "file_pattern": "*Banco Popular*"
  },
  "Dart Bank": {
    "date_column": "Transaction Date",
    "amount_column": "Amount",
    "merchant_column": "Merchant",
    "description_column": "Description"
  }
}
```

### Processing Log Example

```
2026-03-23 14:35:22 - INFO - Processing statement: Banco-Popular-Joint-2026-03.csv
2026-03-23 14:35:23 - INFO - Bank detected: Banco Popular
2026-03-23 14:35:23 - INFO - Format: Spanish bank statement with debit/credit columns
2026-03-23 14:35:24 - INFO - Parsed 15 transactions successfully
2026-03-23 14:35:24 - INFO - Format mapping saved to .statement-formats.json
2026-03-23 14:35:24 - INFO - Organization: Personal/Joint/Banks/
```

### FreshBooks Match Report (CSV)

```
MATCHED INVOICES - AUTO-MARKED PAID
Date,Amount,Merchant,Invoice ID,Status
2026-03-02,1200.50,GREEN THUMB DISPENSARY,INV-001234,Marked Paid
2026-03-03,850.00,SUNNY SIDE COLLECTIVE,INV-001235,Marked Paid

AMBIGUOUS MATCHES - NEEDS REVIEW
Date,Amount,Merchant,Possible Invoices,Recommendation
2026-03-08,2100.75,GROW THERAPY LLC,INV-001236 | INV-001237,Review both and confirm

UNMATCHED TRANSACTIONS - INVESTIGATE
Date,Amount,Merchant,Action
2026-03-10,25.00,BANK FEE,No matching invoice found
```

## 🚀 Next Steps

1. **✓ Test:** Process sample statements and review logs
2. **✓ Calibrate:** Review anomaly detection flagged items
3. **✓ Configure:** Add FreshBooks credentials for auto-marking
4. **✓ Deploy:** Move real statements into folders
5. **✓ Automate:** Schedule processing for 1st of month (Portal42 payroll date)

## 💡 Tips

- **Naming matters:** Name statements clearly (e.g., `Banco-Popular-Joint-2026-03.csv`)
- **Consistent formats:** Try to keep statement CSVs from the same bank in the same format
- **Check logs first:** Before investigating issues, check the processing logs
- **Review flagged items:** Anomaly detection helps catch fraud early
- **Learn-once pattern:** After first processing, future statements auto-parse

## 🆘 Troubleshooting

**"Format not recognized"**
- The skill will ask you to identify columns once
- After that, it's learned forever
- Delete `.statement-formats.json` to reset

**"No matches found"**
- Normal if invoices have different amounts than transactions
- Check the ambiguous/unmatched sheets in the report

**"FreshBooks API error"**
- Check `.freshbooks-config.json` exists
- Verify API token is valid
- Check logs for specific error message

## 📞 Need Help?

- Review the comprehensive SKILL.md documentation
- Check logs in `/Statements/Logs/` for detailed error messages
- Ask Claude to process statements and explain the results

---

**Ready to test?** Start with the sample statements and work your way up to real data! 🚀
