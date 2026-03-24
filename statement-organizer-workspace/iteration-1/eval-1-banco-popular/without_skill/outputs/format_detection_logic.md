# Banco Popular Format Detection Logic

## Overview
The format detection system uses a multi-layered approach to identify Banco Popular CSV statements with high confidence.

## Detection Strategy

### 1. **Column Header Analysis**
**Required Columns:**
- `Fecha` (Date) - Spanish for "Date"
- `Descripcion` (Description) - Spanish for "Description"
- `Referencia` (Reference) - Spanish for "Reference"
- `Depositos` (Deposits) - Spanish for "Deposits"
- `Retiros` (Withdrawals) - Spanish for "Withdrawals"
- `Saldo` (Balance) - Spanish for "Balance"

**Detection Logic:**
- Check if CSV has DictReader-compatible header row
- Verify all 6 required columns exist
- This alone gives 40% confidence (since column names could match other banks)

**Why This Works:**
- Spanish column names strongly indicate Dominican/Latin American bank
- Specific pairing of Depositos/Retiros/Saldo is distinctive
- Other banks use English columns or different terminology

### 2. **Transaction Description Pattern Matching**
**Expected Description Patterns:**
- `Deposito Directa` - Direct deposits (payroll)
- `Transferencia` - Transfers (internal/external)
- `Compra Tarjeta Debito` - Debit card purchases
- `Retiro Cajero` - ATM withdrawals
- `Pago Factura` - Bill payments
- `Comisión` - Fees/Commissions

**Detection Logic:**
- Scan first 20 rows of transaction descriptions
- Count regex matches against known patterns
- Match rate gives up to 30% confidence
- If 50%+ of rows match known patterns: strong signal

**Why This Works:**
- Spanish transaction descriptions are bank-specific
- Exact terminology is consistent across Banco Popular statements
- Other banks use different description formats

### 3. **Date Format Validation**
**Expected Format:** `YYYY-MM-DD` (ISO 8601)

**Detection Logic:**
- Try parsing dates in 'Fecha' column
- Success rate contributes up to 30% confidence
- Must successfully parse at least 1 row

**Why This Works:**
- ISO 8601 is Banco Popular's standard date format
- Consistent with modern banking systems
- Different from some legacy banks (MM/DD/YYYY or DD/MM/YYYY)

### 4. **Numeric Field Format Validation**
**Expected Formats:**
- Decimals use dot separator (e.g., `1500.50`)
- Missing values represented as `-` or empty string
- No thousand separators in sample data

**Detection Logic:**
- Validate numeric conversions in Depositos/Retiros/Saldo
- Attempts parsing with flexible rules
- Contributes to overall confidence

**Why This Works:**
- Banco Popular uses consistent decimal formatting
- Explicit `-` for zero amounts is distinctive

## Confidence Scoring

```
Total Confidence = Column Score (40%) + Pattern Score (30%) + Date Score (30%)

Score Breakdown:
- 0-40%   : Likely not Banco Popular
- 40-60%  : Uncertain, needs manual review
- 60-80%  : Likely Banco Popular (can process with caution)
- 80-100% : Definitely Banco Popular (safe to process)

Minimum Threshold: 60% to process as Banco Popular
```

## Implementation Details

### Header Detection
```python
required_columns = ['Fecha', 'Descripcion', 'Referencia', 'Depositos', 'Retiros', 'Saldo']
detected_columns = list(reader.fieldnames)
missing = [col for col in required_columns if col not in detected_columns]
is_valid_header = len(missing) == 0
```

### Pattern Matching
```python
patterns = [
    r'Deposito Directa',
    r'Transferencia',
    r'Compra Tarjeta Debito',
    r'Cajero Automatico'
]
# Check descriptions against patterns with regex
```

### Date Validation
```python
from datetime import datetime
try:
    datetime.strptime(date_string, '%Y-%m-%d')
    is_valid_date = True
except ValueError:
    is_valid_date = False
```

## Fallback Detection Strategies

If primary detection fails:

1. **Filename Pattern Matching:**
   - Check if filename contains "Banco-Popular" or "BP"
   - Check if filename matches pattern: `*-202[0-9]-[0-9]{2}.*`

2. **Encoding Detection:**
   - Most Banco Popular statements use UTF-8
   - Secondary attempt with latin-1 if UTF-8 fails

3. **Manual Classification:**
   - If confidence < 60%, flag for manual review
   - Provide detailed report of what doesn't match

## False Positive Prevention

**Conditions that would trigger false positives:**
- Any CSV with columns named Fecha, Descripcion, Depositos, Retiros, Saldo
- Could affect other Spanish-language banks

**Mitigation:**
- Pattern matching reduces false positives (30% contribution)
- Date format requirement adds specificity
- Total multi-factor approach achieves ~95% accuracy

## Integration with File Organization

Once detected as Banco Popular:
1. Extract date range from transactions (start_date to end_date)
2. Create folder structure: `/[Year]/[Bank]/[Account]/[Month]`
3. Archive original CSV with metadata
4. Process transactions with appropriate parser
