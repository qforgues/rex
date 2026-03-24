---
name: statement-organizer
description: |
  Organize and automate your financial statement management. Use this skill whenever you have bank or credit card statements to process — whether you're organizing Banco Popular or Dart Bank statements into folders, learning statement formats automatically, or syncing Dart Bank transactions with FreshBooks to mark invoices as paid. This skill handles format detection, learns new statement types once and remembers them forever, and integrates with FreshBooks to eliminate manual invoice reconciliation. Trigger this skill whenever you drop statements into your Statements folder, or when you want to sync unpaid Portal42 invoices with your Dart Bank account.

compatibility: |
  - Python 3.8+
  - CSV parsing (built-in)
  - FreshBooks API access (requires API token)
  - Folder structure: `/Statements/Personal/{Joint,You,Courtney}/{Banks,Credit_Cards}`, `/Business-{You,Courtney}/{Banks,Credit_Cards}`
---

## Overview

This skill automates your financial statement workflow:

1. **Format Learning**: Drop a statement file and the skill detects the bank/card, learns its format (column headers, data layout), and stores the mapping for future use.
2. **Statement Organization**: Automatically moves or identifies where statements belong in your folder structure based on account type.
3. **FreshBooks Sync**: For Dart Bank statements, extracts transactions and matches them against unpaid Portal42 invoices by amount + dispensary name. Marks matching invoices as paid via FreshBooks API.
4. **Logging**: Creates detailed logs of all operations, including matches found, ambiguities flagged, and any errors.

The goal is **zero manual intervention** — once you set up format mappings and FreshBooks auth, you just drop statements and the skill does the rest.

---

## Setup (One-Time)

### 1. FreshBooks API Token

You need your FreshBooks API token. Here's how to provide it to the skill:

**Option A: Environment Variable (Recommended)**
```bash
export FRESHBOOKS_API_TOKEN="your-api-token-here"
```

**Option B: Config File**
Create a file at `/Statements/.freshbooks-config.json`:
```json
{
  "api_token": "your-token-here",
  "account_id": "your-account-id"
}
```

The skill will read this file and never ask again.

### 2. Folder Structure

The skill expects your statements to live in:
```
/Statements/
├── Personal/
│   ├── Joint/
│   │   ├── Banks/       ← Banco Popular joint statements go here
│   │   └── Credit_Cards/
│   ├── You/
│   │   ├── Banks/       ← Banco Popular personal statements go here
│   │   └── Credit_Cards/
│   └── Courtney/
│       ├── Banks/
│       └── Credit_Cards/
├── Business-You/
│   ├── Banks/           ← Dart Bank Portal42 statements go here
│   └── Credit_Cards/
├── Business-Courtney/
│   ├── Banks/
│   └── Credit_Cards/
└── Logs/                ← Automatically created; stores all operation logs
```

---

## How It Works

### Format Detection & Learning

When you drop a CSV statement, the skill:

1. **Reads the first few rows** to detect the bank/card type (looks for known headers like "Banco Popular", "Dart", "Merchant", "Amount", etc.)
2. **Creates a mapping** that captures:
   - Bank/card identifier
   - Transaction date column(s)
   - Amount column
   - Merchant/description column
   - Any other relevant fields
3. **Stores the mapping** in `/Statements/.statement-formats.json` so future statements of the same type are parsed instantly

**Example mapping file:**
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
    "description_column": "Description",
    "file_pattern": "*Dart*"
  }
}
```

If the skill encounters a format it doesn't recognize, it will ask you to identify the columns manually. This happens **only once per bank/card** — after that, it's automatic forever.

### FreshBooks Matching (Dart Bank Only)

When processing Dart Bank statements, the skill:

1. **Extracts all transactions** from the statement
2. **Fetches unpaid invoices** from FreshBooks for your Portal42 account
3. **Matches transactions to invoices** by:
   - Transaction amount = Invoice total
   - Transaction merchant/description contains the dispensary name
4. **For perfect matches**: Automatically marks the invoice as paid via FreshBooks API
5. **For ambiguous matches**: Flags them in a CSV report for your review (e.g., "$500 transaction" might match multiple invoices)
6. **For unmatched transactions**: Lists them so you can investigate

All results are logged with timestamps.

---

## Usage

### Basic: Process a Statement File

**When to use**: You've dropped a new CSV statement into one of your `Banks/` or `Credit_Cards/` folders.

Prompt:
```
Process the statement file at /Statements/Personal/Joint/Banks/Banco-Popular-March-2026.csv
```

The skill will:
- Detect it's a Banco Popular statement
- Learn/apply the format mapping
- Extract transactions
- Log results to `/Statements/Logs/statement-processing-2026-03-23.log`
- (If it's Dart Bank) Sync to FreshBooks and report matches/mismatches

### Advanced: Review Flagged Matches

After running the skill on a Dart Bank statement, check for a report file:
```
/Statements/Logs/freshbooks-matches-2026-03-23.csv
```

This CSV contains three sheets:
- **Matched**: Transactions automatically marked as paid (no action needed)
- **Ambiguous**: Transactions with multiple possible invoice matches (review & tell me which to mark paid)
- **Unmatched**: Transactions with no invoice match (investigate or ignore)

If you find mistakes (e.g., a transaction was mismatched), edit the CSV and prompt:
```
I've reviewed the matches in /Statements/Logs/freshbooks-matches-2026-03-23.csv.
Here are the corrections:
- Row 15: This transaction should match invoice #ABC-123 instead
- Row 22: This is a duplicate, don't mark it paid

Please update FreshBooks accordingly.
```

### Learning New Formats

If you have a new bank or card the skill hasn't seen before:

Prompt:
```
I've added a new statement file: /Statements/Personal/You/Banks/NewBank-March-2026.csv
Please learn the format and add it to the mappings.
```

The skill will guide you through identifying columns, then save the mapping for future use.

---

## Logs & Reports

All operations are logged to `/Statements/Logs/`:

- **statement-processing-YYYY-MM-DD.log** — General processing log (files read, formats detected, errors)
- **freshbooks-sync-YYYY-MM-DD.log** — FreshBooks API calls, matches found, invoices marked paid
- **freshbooks-matches-YYYY-MM-DD.csv** — Detailed match report with all ambiguities and unmatched transactions

You can review these anytime to see what happened.

---

## Troubleshooting

### "API token not found"
Make sure you've set `FRESHBOOKS_API_TOKEN` as an environment variable or created `.freshbooks-config.json`.

### "Statement format not recognized"
The skill will ask you to identify the columns in the statement. Once you do, it's learned forever.

### "No matches found for Dart Bank transactions"
This is normal if your invoices have different amounts than your transactions (e.g., partial payments, fees). Check the "Unmatched" sheet in the CSV report.

### "FreshBooks API returned an error"
Check the log file — it will show the exact error. Common issues:
- Token expired (regenerate in FreshBooks)
- Invoice already marked paid (safe to ignore)
- Wrong account ID (verify in `.freshbooks-config.json`)

---

## What Happens Under the Hood

1. **File Detection**: When you drop a file, the skill checks its location (which `/Statements/` subfolder) and filename to infer account type.
2. **Format Parsing**: Uses the stored mapping (or creates a new one) to extract:
   - Date
   - Amount
   - Merchant/Description
3. **FreshBooks Lookup**: (Dart Bank only) Fetches unpaid invoices with portal details
4. **Matching Algorithm**:
   - Exact amount match first
   - Then merchant name fuzzy matching (e.g., "DISPENSARY ABC" matches invoice for "ABC Dispensary")
   - Confidence threshold: 90% for auto-mark, <90% flagged as ambiguous
5. **Logging**: Every operation is timestamped and logged
6. **Report Generation**: CSV with all matches, ambiguities, and unmatched transactions

---

## Tips for Best Results

- **Consistent file naming**: Name statements with the bank/month (e.g., `Banco-Popular-Joint-2026-03.csv`, `Dart-Bank-2026-03.csv`). The skill uses this to detect the account type.
- **Check logs regularly**: After each run, peek at the log file to catch any anomalies early.
- **Review FreshBooks matches**: Always skim the "Ambiguous" sheet to ensure accuracy, especially early on.
- **Keep format mappings updated**: If your bank changes its statement format, just process one statement and the skill will auto-update the mapping.

---

## FAQ

**Q: Can the skill organize statements without processing them?**
A: Yes, if you just want to move/organize files without FreshBooks sync, the skill can do that. Just specify the account type and the skill will file it correctly.

**Q: What if an invoice is already marked paid in FreshBooks?**
A: The skill skips it — FreshBooks will return an error, which is harmless and logged.

**Q: Can I use this skill for credit cards too?**
A: Yes! The format learning works for any CSV statement. The FreshBooks sync only applies to Dart Bank (Portal42), but you can organize credit card statements into the right folders.

**Q: What if I have a transaction that should mark multiple invoices as paid?**
A: The skill will flag this in the "Ambiguous" report. You review it and tell me which invoice to mark, then I'll update FreshBooks. This is intentional — you have final say on multi-invoice matches.

**Q: How do I delete or reset a learned format?**
A: Edit `/Statements/.statement-formats.json` and remove that bank's entry. Next time you process a statement from that bank, the skill will re-learn it.
