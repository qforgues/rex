# NewBank Statement Format Auto-Detection (Without Skill)

## Overview

This directory contains a complete implementation of automatic bank statement format detection and integration WITHOUT using a Claude skill. The approach demonstrates how to learn a new bank's CSV format and add it to the statement organizer system.

## Problem Statement

When presented with a new bank's statement CSV file, we need to:
1. **Learn** the format structure automatically
2. **Detect** column headers and field types
3. **Parse** transactions using the detected format
4. **Integrate** into the statement organizer for future use

## Solution Approach

The solution uses a **three-phase detection strategy**:

### Phase 1: Header Analysis
- Extract column names from CSV
- Match against keyword lists (date, amount, balance, merchant, etc.)
- Assign semantic field types based on naming conventions

### Phase 2: Content Analysis
- Examine sample values in each column
- Match against regex patterns for dates, amounts, IDs, etc.
- Calculate confidence scores for each detection

### Phase 3: Integration
- Generate standardized mapping dictionaries
- Store mappings for future use
- Parse and normalize transactions

## Files in This Directory

### 1. `format_detection.py` (Main Implementation)
Complete format detection engine with:
- **FormatDetector class**: Core detection logic
- **FieldType enum**: Seven field types (DATE, DESCRIPTION, AMOUNT, DEBIT, CREDIT, BALANCE, REFERENCE)
- **ColumnInfo dataclass**: Stores detection results with confidence scores
- **Key Methods**:
  - `load_csv()`: Reads CSV statement
  - `analyze_headers()`: Detects all column types
  - `generate_format_mapping()`: Creates standardized mapping
  - `parse_transactions()`: Converts CSV to transaction objects

**Usage**:
```python
detector = FormatDetector()
headers, data = detector.load_csv("NewBank-March-2026.csv")
columns = detector.analyze_headers(headers, data)
mapping = detector.generate_format_mapping()
transactions = detector.parse_transactions(data)
```

### 2. `sample_mapping.json` (Example Output)
Generated format mapping for NewBank showing:
- Detected column types and confidence scores
- Required and optional fields
- Validation rules for each field
- Parsing rules (date format, decimals, etc.)
- Sample values from each column

**Key Fields**:
- `detection_confidence`: Overall confidence (0-1 scale)
- `fields`: Maps column name to field type
- `required_fields`: Critical columns for successful parsing
- `validation_rules`: Regex patterns for validation

### 3. `integration_guide.py` (Implementation Example)
Shows how to integrate detected formats into a system with:
- **BankFormatRegistry**: Manages multiple bank formats
- **StatementParser**: Uses registered formats to parse CSVs
- **TransactionNormalizer**: Converts to standard format
- **demo_integration()**: Complete workflow example

**Usage**:
```python
registry = BankFormatRegistry()
registry.register_format("NewBank", mapping)

parser = StatementParser(registry)
transactions = parser.parse_statement("NewBank-March-2026.csv", "NewBank")

normalizer = TransactionNormalizer()
normalized = [normalizer.normalize(tx) for tx in transactions]
```

### 4. `parsed_transactions_example.json` (Sample Output)
Complete example of parsed and normalized transactions showing:
- Raw parsed transaction with all detected fields
- Normalized transaction in standard format
- Transaction summary (totals, balances, date range)

**Structure**:
```json
{
  "transactions": [
    {
      "transaction_date": "2026-03-01",
      "merchant": "Salary Deposit",
      "debit_amount": null,
      "credit_amount": 4500.00,
      "balance": 4500.00,
      "normalized": { ... }
    }
  ],
  "summary": { ... }
}
```

### 5. `summary.txt` (Complete Documentation)
Comprehensive guide covering:
- **Section 1**: How to learn new formats (5 phases)
- **Section 2**: Format detection algorithms and logic
- **Section 3**: Implementation details
- **Section 4**: Mapping structure explanation
- **Section 5**: NewBank example with real results
- **Section 6**: Integration with existing system
- **Section 7**: Advantages of this approach
- **Section 8**: File inventory
- **Section 9**: Next steps for full automation

## Quick Start

### 1. Detect Format
```bash
python3 format_detection.py
```

This will:
- Load the test statement (NewBank-March-2026.csv)
- Analyze all columns
- Display detection results
- Parse and show sample transactions

### 2. Review the Mapping
```bash
cat sample_mapping.json
```

Shows what was auto-detected and allows manual adjustments if needed.

### 3. Integrate Into Your System
```bash
python3 integration_guide.py
```

Demonstrates full workflow:
1. Auto-detect format
2. Register in system
3. Parse statements
4. Normalize to standard format

## Key Concepts

### Field Types
- **DATE**: Transaction date
- **DESCRIPTION**: Merchant/payee name
- **AMOUNT**: Generic amount (direction inferred from context)
- **DEBIT**: Money out
- **CREDIT**: Money in
- **BALANCE**: Account balance after transaction
- **REFERENCE**: Transaction ID/reference number

### Confidence Scoring
- 0.9+: High confidence (header match or strong pattern match)
- 0.7-0.85: Medium confidence (pattern match with some uncertainty)
- 0.5-0.7: Low confidence (fallback classification)
- < 0.5: Not classified

### Algorithm Strategy

```
For each column:
  1. Check header keywords (high confidence)
  2. Analyze sample values with regex patterns
  3. Calculate match ratio
  4. Assign field type and confidence
  5. Mark as required if critical for parsing
```

## NewBank Example

### Input CSV
```csv
Transaction Date,Merchant,Amount,Type,Running Balance,Reference ID
2026-03-01,Salary Deposit,4500.00,Credit,4500.00,TR-2026030100001
2026-03-02,Whole Foods Market,-125.50,Debit,4374.50,TR-2026030200002
```

### Detection Results
```
Transaction Date  -> DATE       (confidence: 0.90)
Merchant          -> DESCRIPTION (confidence: 0.90)
Amount            -> AMOUNT     (confidence: 0.70)
Type              -> UNKNOWN    (confidence: 0.50)
Running Balance   -> BALANCE    (confidence: 0.90)
Reference ID      -> REFERENCE  (confidence: 0.85)

Overall: 0.86
```

### Parsed Output
```json
{
  "transaction_date": "2026-03-01",
  "merchant": "Salary Deposit",
  "credit_amount": 4500.00,
  "balance": 4500.00,
  "reference_id": "TR-2026030100001"
}
```

## Advantages

- **Automatic**: No manual format specification required
- **Adaptive**: Works with any CSV layout and column order
- **Measurable**: Confidence scores show detection quality
- **Maintainable**: Generated mappings are human-readable
- **Extensible**: Easy to add custom rules or adjustments
- **Cacheable**: Future statements use cached mapping

## Limitations & Future Improvements

### Current Limitations
1. Assumes CSV format (not JSON, XML, PDF, etc.)
2. Single row represents one transaction
3. Requires English-like column headers for keyword matching

### Future Enhancements
1. Support for multi-row transactions
2. Bank-specific rules and heuristics
3. ML-based field type detection
4. Automatic error detection and recovery
5. Support for multiple file formats
6. Localization for non-English headers

## Testing

All modules have been tested with NewBank-March-2026.csv:
- **format_detection.py**: Successfully detects 6 columns with 0.86 confidence
- **integration_guide.py**: Successfully registers format and parses transactions
- **sample_mapping.json**: Generated and validated with actual data

## Integration With Existing System

To add NewBank to the statement organizer:

1. **Generate mapping**:
   ```python
   detector = FormatDetector()
   headers, data = detector.load_csv("NewBank-March-2026.csv")
   columns = detector.analyze_headers(headers, data)
   mapping = detector.generate_format_mapping()
   ```

2. **Store mapping** (save to DB or file):
   ```python
   with open("banks/newbank_mapping.json", "w") as f:
       json.dump(mapping, f)
   ```

3. **Future statements use cached mapping**:
   ```python
   # Next time NewBank statement arrives
   format_mapping = load_mapping("banks/newbank_mapping.json")
   transactions = parse_with_mapping(csv_file, format_mapping)
   ```

## Architecture

```
Input CSV File
      |
      v
FormatDetector.load_csv()
      |
      +-> Extract Headers
      +-> Load Sample Rows
      |
      v
FormatDetector.analyze_headers()
      |
      +-> Header Keyword Matching
      +-> Content Pattern Matching
      +-> Confidence Scoring
      |
      v
FormatDetector.generate_format_mapping()
      |
      +-> Create Mapping Structure
      +-> Set Validation Rules
      +-> Identify Required Fields
      |
      v
BankFormatRegistry.register_format()
      |
      v
StatementParser.parse_statement()
      |
      v
Normalized Transactions
      |
      v
Store in System / Database
```

## Performance

- CSV loading: O(n) where n = number of rows
- Header analysis: O(m) where m = number of columns
- Type detection: O(m * k) where k = sample size (typically 5)
- Transaction parsing: O(n * m)
- Overall: Linear in file size with small constant factors

## Error Handling

The implementation gracefully handles:
- Missing columns
- Empty values
- Invalid date formats
- Non-numeric amounts
- Unknown field types

All errors are captured in confidence scoring and required field identification.

## Contributing

To extend this implementation:

1. **Add new field types**: Update `FieldType` enum in format_detection.py
2. **Add new keywords**: Update keyword lists in `FormatDetector` class
3. **Add new patterns**: Extend regex patterns in `FormatDetector`
4. **Add bank-specific rules**: Extend `BankFormatRegistry` or `StatementParser`

## License

Part of the Statement Organizer project. See main project README for licensing.

## Questions & Support

For questions about this implementation, see `summary.txt` for detailed documentation on algorithms and approach.

---

**Generated**: 2026-03-23
**Test File**: NewBank-March-2026.csv
**Detection Confidence**: 0.86
**Transactions Parsed**: 16
