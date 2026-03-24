# Format Learning & Auto-Detection Process

## Overview
When you provide a new bank statement, the skill uses intelligent pattern matching to automatically learn and remember the format, making future processing instant and hands-free.

## Step-by-Step Auto-Detection Logic

### 1. **Bank Identification (Detection Phase)**
The skill first identifies which bank the statement comes from using two strategies:

**Strategy A: Filename Analysis**
- Extracts the filename and converts to lowercase
- Looks for bank name keywords (e.g., "NewBank", "Dart", "Banco")
- Example: `NewBank-March-2026.csv` → detects **"NewBank"**

**Strategy B: CSV Header Analysis**
- If filename doesn't reveal the bank, reads the first row of headers
- Converts header names to lowercase and searches for bank identifiers
- Acts as a fallback when filename is generic (e.g., `statement-2026-03.csv`)

### 2. **Column Discovery (Learning Phase)**
Once the bank is identified, the skill reads the CSV header row and maps columns using pattern matching:

#### Pattern Matching Strategy
The skill maintains a list of common patterns for each column type and searches headers for substring matches:

**Date Column Patterns**
- Looks for: `fecha`, `date`, `transaction date`, `posted date`, `post date`
- **NewBank Match**: "Post Date" contains pattern "date" → `date_column: "Post Date"`

**Amount Column Patterns**
- Looks for: `monto`, `amount`, `total`, `valor`, `transaction`
- **NewBank Match**: "Debit Amount" contains pattern "amount" → `amount_column: "Debit Amount"`

**Merchant/Description Patterns**
- Looks for: `merchant`, `descripción`, `description`, `vendor`, `payee`, `name`
- **NewBank Match**: "Merchant Name" contains pattern "merchant" → `merchant_column: "Merchant Name"`

**Debit/Credit Patterns**
- Looks for: `debit`, `débito`, `credit`, `crédito`
- **NewBank Match**: "Debit Amount" → `debit_amount_column: "Debit Amount"`
- **NewBank Match**: "Credit Amount" → `credit_amount_column: "Credit Amount"`

### 3. **Validation (Confidence Check)**
After pattern matching, the skill validates that essential columns were found:

```python
if 'date_column' in mapping and 'amount_column' in mapping:
    confidence = "high"  # All essential fields found
    save_mapping()       # Store for future use
else:
    confidence = "low"   # Manual user input required
    prompt_user()        # Ask user to identify columns
```

**For NewBank example:**
- ✓ Date column found: "Post Date"
- ✓ Amount column found: "Debit Amount"
- ✓ Merchant column found: "Merchant Name"
- **Result**: High confidence → Auto-saves mapping

### 4. **Format Storage (Memory Phase)**
The learned format is stored in `.statement-formats.json` in your Statements directory:

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
    "detected_fields": [list of all CSV headers],
    "auto_detection_confidence": "high",
    "detection_timestamp": "2026-03-23T11:47:00Z"
  }
}
```

**Key Fields:**
- `date_column`: Which CSV column contains transaction dates
- `amount_column`: Which CSV column contains transaction amounts (primary)
- `debit_amount_column` / `credit_amount_column`: For split-column formats (debits and credits separate)
- `merchant_column`: Which CSV column contains merchant/payee names
- `file_pattern`: Glob pattern to match future statements of this bank (e.g., `*NewBank*`)
- `detected_fields`: Complete list of all column headers found (for reference and debugging)
- `auto_detection_confidence`: Whether the detection was "high" (automatic) or "low" (manual)

## Future Processing (Automatic Parsing)

Once a format is learned and stored, all future NewBank statements are processed instantly:

### Flow for Next Statement
```
1. New file: NewBank-April-2026.csv
2. Filename check: "newbank" matches "NewBank" entry in .statement-formats.json
3. Mapping lookup: Found! Use stored format
4. Parse rows: Extract date, amount, merchant using mapped columns
5. Return transactions: No learning needed, instant parsing
```

### Example Parsing with Learned Format

**Input CSV Row:**
```
TXN005,2026-03-07,ONLINE RETAILER,Shopping Purchase,249.99,,5532.08
```

**Applied Mapping:**
- `Post Date` (date_column) → "2026-03-07"
- `Debit Amount` (debit_amount_column) → 249.99 (converted to -249.99 for debit)
- `Merchant Name` (merchant_column) → "ONLINE RETAILER"
- `Description` (description_column) → "Shopping Purchase"

**Output Transaction Object:**
```python
{
  'date': '2026-03-07',
  'amount': -249.99,  # Negative because it's a debit
  'merchant': 'ONLINE RETAILER',
  'raw_row': {original CSV row}
}
```

## Advantages of This Approach

1. **One-Time Learning**: Format is learned once, remembered forever
2. **Automatic**: No manual intervention after the first statement
3. **Intelligent**: Uses pattern matching to handle column name variations
4. **Resilient**: Falls back to manual setup if patterns don't match
5. **Traceable**: Stores detection timestamp and confidence level for auditing
6. **Flexible**: Supports both single-amount and debit/credit split formats
7. **Extensible**: New patterns can be added as you encounter new banks

## When Manual Identification is Needed

If the skill cannot auto-detect (low confidence), it will ask you:

```
Format not recognized for NewBank. Please identify these columns:
- Which column contains the transaction DATE? (e.g., "Post Date")
- Which column contains the transaction AMOUNT? (e.g., "Debit Amount")
- Which column contains the MERCHANT/description? (e.g., "Merchant Name")
```

Once you identify them, the skill saves the mapping and never asks again for that bank.

## Updating Formats

If your bank changes its statement format:
1. Process one new statement from that bank
2. The skill re-learns the format automatically
3. Updated mapping is stored in `.statement-formats.json`
4. You can see what changed in the detection_timestamp

To manually reset a format:
- Edit `.statement-formats.json` and delete the bank's entry
- Next time you process a statement from that bank, it will re-learn
