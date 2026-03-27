# NewBank Format Mapping - Detailed Walkthrough

## CSV Header Analysis

### Raw CSV Headers (from NewBank-March-2026.csv)
```
Transaction ID, Post Date, Merchant Name, Description, Debit Amount, Credit Amount, Running Balance
```

### Column Discovery Process

The skill reads each header and matches it against pattern lists:

| Header | Pattern Checked | Match? | Assigned To |
|--------|---|---|---|
| Transaction ID | date, amount, merchant, debit, credit | None | (ignored - not needed) |
| Post Date | date, posted date, fecha, transaction date | ✓ date | **date_column** |
| Merchant Name | merchant, payee, vendor, description | ✓ merchant | **merchant_column** |
| Description | description, descripción, notes | ✓ description | **description_column** |
| Debit Amount | amount, debit, débito, monto | ✓ amount, ✓ debit | **amount_column**, **debit_amount_column** |
| Credit Amount | amount, credit, crédito, monto | ✓ amount, ✓ credit | **credit_amount_column** |
| Running Balance | (not checked - not essential) | N/A | (ignored) |

### Confidence Calculation
```python
Essential fields required:
✓ date_column = "Post Date"
✓ amount_column = "Debit Amount"

Result: Confidence = HIGH
Action: Auto-save mapping (no user prompt needed)
```

---

## Complete Format Mapping Stored

When the format is learned, this mapping is saved to `/Statements/.statement-formats.json`:

```json
{
  "NewBank": {
    "date_column": "Post Date",
    "amount_column": "Debit Amount",
    "merchant_column": "Merchant Name",
    "description_column": "Description",
    "debit_amount_column": "Debit Amount",
    "credit_amount_column": "Credit Amount",
    "file_pattern": "*NewBank*",
    "detected_fields": [
      "Transaction ID",
      "Post Date",
      "Merchant Name",
      "Description",
      "Debit Amount",
      "Credit Amount",
      "Running Balance"
    ],
    "auto_detection_confidence": "high",
    "detection_timestamp": "2026-03-23T11:47:00Z",
    "learning_notes": "Format auto-detected successfully. Bank uses separate Debit/Credit columns with Post Date as transaction date. Merchant name field provided. All essential fields identified."
  }
}
```

---

## Transaction Extraction Using Learned Format

### Example: First Transaction in Statement

**Raw CSV Row:**
```
TXN001,2026-03-01,ABC COFFEE SHOP,Coffee & Breakfast,5.50,,2994.50
```

**Extraction Process:**

1. **Date Extraction**
   ```
   Field: format_info['date_column'] = "Post Date"
   Row Value: row["Post Date"] = "2026-03-01"
   Result: transaction['date'] = "2026-03-01"
   ```

2. **Merchant Extraction**
   ```
   Field: format_info['merchant_column'] = "Merchant Name"
   Row Value: row["Merchant Name"] = "ABC COFFEE SHOP"
   Result: transaction['merchant'] = "ABC COFFEE SHOP"
   ```

3. **Description Extraction**
   ```
   Field: format_info['description_column'] = "Description"
   Row Value: row["Description"] = "Coffee & Breakfast"
   Result: transaction['description'] = "Coffee & Breakfast"
   ```

4. **Amount Extraction (Debit/Credit Split)**
   ```
   Check debit_amount_column:
     Field: "Debit Amount"
     Value: row["Debit Amount"] = "5.50"
     Present: YES

   Check credit_amount_column:
     Field: "Credit Amount"
     Value: row["Credit Amount"] = ""
     Present: NO

   Action: Use debit amount, make it negative
   Calculation: -float("5.50".replace(',', '').replace('$', '')) = -5.50
   Result: transaction['amount'] = -5.50
   Type: 'debit' (negative amount)
   ```

**Extracted Transaction Object:**
```python
{
  'date': '2026-03-01',
  'amount': -5.50,
  'merchant': 'ABC COFFEE SHOP',
  'description': 'Coffee & Breakfast',
  'type': 'debit',
  'raw_row': {
    'Transaction ID': 'TXN001',
    'Post Date': '2026-03-01',
    'Merchant Name': 'ABC COFFEE SHOP',
    'Description': 'Coffee & Breakfast',
    'Debit Amount': '5.50',
    'Credit Amount': '',
    'Running Balance': '2994.50'
  }
}
```

---

## Example: Credit Transaction

**Raw CSV Row:**
```
TXN002,2026-03-02,SALARY DEPOSIT,Monthly Salary,,3000.00,5994.50
```

**Extraction Process:**

1. Date: "2026-03-02" (same logic)
2. Merchant: "SALARY DEPOSIT"
3. Description: "Monthly Salary"
4. Amount:
   ```
   Check debit_amount_column:
     Field: "Debit Amount"
     Value: row["Debit Amount"] = ""
     Present: NO

   Check credit_amount_column:
     Field: "Credit Amount"
     Value: row["Credit Amount"] = "3000.00"
     Present: YES

   Action: Use credit amount as-is
   Calculation: float("3000.00") = 3000.00
   Result: transaction['amount'] = 3000.00
   Type: 'credit' (positive amount)
   ```

**Extracted Transaction Object:**
```python
{
  'date': '2026-03-02',
  'amount': 3000.00,
  'merchant': 'SALARY DEPOSIT',
  'description': 'Monthly Salary',
  'type': 'credit',
  'raw_row': { ... }
}
```

---

## Automatic Parsing Flow for Future Statements

### When NewBank-April-2026.csv Arrives

```
Step 1: File Detection
  Input: NewBank-April-2026.csv
  Action: Extract filename, convert to lowercase
  Result: "newbank" detected

Step 2: Format Lookup
  Input: Bank name "NewBank"
  Action: Check .statement-formats.json for "NewBank" entry
  Result: ✓ Found! Format already learned

Step 3: Load Mapping (from memory)
  date_column: "Post Date"
  amount_column: "Debit Amount"
  merchant_column: "Merchant Name"
  description_column: "Description"
  debit_amount_column: "Debit Amount"
  credit_amount_column: "Credit Amount"

Step 4: Parse Rows
  For each CSV row:
    - Extract date from "Post Date"
    - Extract merchant from "Merchant Name"
    - Extract description from "Description"
    - Extract amount from "Debit Amount" or "Credit Amount"
    - Return transaction object

Step 5: Return Parsed Transactions
  All transactions ready for processing/reporting
  No re-learning, no user prompts
  100% automatic
```

---

## Comparison: Before and After Learning

### BEFORE Learning (First Statement)

```
User input: "Process NewBank-March-2026.csv"

Skill workflow:
1. Detect bank: "NewBank"
2. Check formats: Not in .statement-formats.json
3. Read CSV headers: [Transaction ID, Post Date, Merchant Name, ...]
4. Pattern match: All patterns match successfully ✓
5. High confidence: Confidence > 90%
6. Auto-save: Store mapping to .statement-formats.json
7. Parse transactions: Extract all data
8. Return: 10 transactions ready
```

Result: First statement processed, format learned, mapping saved

### AFTER Learning (Next Statement)

```
User input: "Process NewBank-April-2026.csv"

Skill workflow:
1. Detect bank: "NewBank"
2. Check formats: ✓ Found in .statement-formats.json!
3. Load mapping: Direct lookup (no re-learning)
4. Parse transactions: Use learned format
5. Return: 10 transactions ready

Time saved: No CSV analysis, no pattern matching, no confidence checking
Automation: 100% hands-off
```

Result: Subsequent statements parsed instantly

---

## Pattern Matching Details

### Date Pattern Lists

The skill searches for these patterns when looking for date columns:

```python
date_patterns = [
    'fecha',           # Spanish
    'date',            # English
    'transaction date', # Specific
    'posted date',      # Bank-specific
    'post date'         # NewBank variant
]
```

**NewBank**: "Post Date" contains "date" → Matched ✓

### Amount Pattern Lists

Patterns for identifying amount columns:

```python
amount_patterns = [
    'monto',      # Spanish
    'amount',     # English
    'total',      # Generic
    'valor',      # Spanish alternative
    'transaction' # Sometimes combined
]
```

**NewBank**: "Debit Amount" contains "amount" → Matched ✓

### Merchant Pattern Lists

Patterns for identifying merchant/payee columns:

```python
merchant_patterns = [
    'merchant',      # Standard
    'descripción',   # Spanish
    'description',   # English
    'vendor',        # Alternative
    'payee',         # Check-specific
    'name'           # Generic fallback
]
```

**NewBank**: "Merchant Name" contains "merchant" → Matched ✓

### Debit/Credit Detection

Patterns for identifying debit/credit columns:

```python
# Debit patterns
for field in fieldnames:
    if 'debit' in field.lower() or 'débito' in field.lower():
        mapping['debit_amount_column'] = field

# Credit patterns
for field in fieldnames:
    if 'credit' in field.lower() or 'crédito' in field.lower():
        mapping['credit_amount_column'] = field
```

**NewBank**:
- "Debit Amount" contains "debit" → `debit_amount_column` ✓
- "Credit Amount" contains "credit" → `credit_amount_column` ✓

---

## Amount Normalization

The skill cleans amounts before storing:

```python
Raw value: "5.50"
Operations:
  1. Remove commas: "5.50"
  2. Remove $ signs: "5.50"
  3. Convert to float: 5.50
  4. Apply sign for debit: -5.50

Raw value: "3,000.00"
Operations:
  1. Remove commas: "3000.00"
  2. Remove $ signs: "3000.00"
  3. Convert to float: 3000.00
  4. No sign change for credit: 3000.00

Result: Normalized amount ready for calculations
```

---

## Extensibility for New Banks

When you encounter a new bank format:

```
1. Drop statement in Statements folder
2. Skill detects unknown bank
3. Skill runs pattern matching on headers
4. If patterns match essential fields:
   - Save format to .statement-formats.json
   - Process statement immediately
   - No future re-learning needed
5. If patterns don't match:
   - Prompt user to identify columns
   - Save user-provided mapping
   - Process statement
   - No future re-learning needed

Either way: Learned once, reused forever
```

---

## Manual Format Reset

If you need to re-learn a format (bank changed its statement layout):

```json
// Current .statement-formats.json
{
  "NewBank": { ... },
  "Dart Bank": { ... }
}

// To reset NewBank:
// Option 1: Delete the entry
{
  "Dart Bank": { ... }
}

// Next time you process NewBank statement:
// Skill will re-learn the format automatically

// Option 2: Use skill prompt
// "Reset the format for NewBank - re-learn it from the next statement"
// Skill will delete entry and re-learn on next processing
```

---

## Summary

The format mapping enables fully automatic statement processing:

1. **Learn Once**: First statement triggers pattern matching and saves mapping
2. **Reuse Forever**: All future statements use the learned format
3. **No Manual Intervention**: Zero prompts or manual column identification
4. **Extensible**: New patterns can be added for new banks
5. **Resilient**: Falls back to manual setup if patterns don't match
6. **Auditable**: Stores timestamp and confidence level for each learning event
7. **Updateable**: Re-learn if bank changes format by processing one new statement

This design achieves the skill's goal: **"Learn it once, remember it forever, process it instantly."**
