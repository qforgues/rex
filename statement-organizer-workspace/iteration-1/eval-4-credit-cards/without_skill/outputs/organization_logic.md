# Credit Card Statement Organization Logic

## Overview
This document describes the approach for handling three different credit card formats: American Express (Business), Chase (Personal), and Visa.

## Format Detection Strategy

### 1. Header-Based Detection
Each card issuer has distinctive statement headers that serve as primary identifiers:

**American Express Business**
- Primary header: "AMERICAN EXPRESS" or "AMEX"
- Features: Membership rewards, expense tracking, business classification
- Field arrangement: Date | Description | Category | Amount

**Chase Personal**
- Primary header: "CHASE" or "JPMORGAN CHASE"
- Features: Ultimate Rewards, simple tabular layout, merchant locations
- Field arrangement: Posted Date | Description | Location | Amount | Type

**Visa**
- Primary header: "VISA" or "VISA INC"
- Features: Debit/Credit indicators, balance forward, reference numbers
- Field arrangement: Date | Description | Reference | Debit/Credit | Amount

### 2. Confidence Scoring
Detection uses a scoring mechanism to handle ambiguous cases:

```
Header match:       +40 points
Feature match:      +10 points per feature
Format alignment:   +5 points per field match
```

Confidence = (total_score / max_possible) × 100%

Minimum confidence threshold: 30% (files below this go to "Unknown" folder)

### 3. Distinctive Feature Recognition

**AmEx Business-Specific:**
- Membership rewards points displayed
- Per-transaction business categories
- Multiple card member support
- Detailed billing cycle tracking

**Chase Personal-Specific:**
- Ultimate Rewards integration
- Merchant city/location information
- Clear closing date marking
- Single cardholder focus

**Visa-Specific:**
- Explicit Debit/Credit indicators (Dr/Cr columns)
- Running balance display
- Balance forward calculations
- International transaction markers
- Multi-currency support

## Organization Structure

### Directory Hierarchy
```
/Statements/Organized/
├── AmEx_Business/
│   ├── [statements organized by date]
│   └── [business expense tracking]
├── Chase_Personal/
│   ├── [statements organized by date]
│   └── [rewards tracking]
├── Visa/
│   ├── [statements organized by date]
│   └── [debit/credit reconciliation]
└── Unknown/
    └── [unclassified statements for review]
```

### Processing Pipeline

1. **Input Collection Phase**
   - Scan `/Statements/Personal/You/Credit_Cards/`
   - Scan `/Statements/Business-You/Credit_Cards/`
   - Collect all statement files (CSV, PDF, XLS, XLSX, TXT)

2. **Detection Phase**
   - Read file content
   - Apply header pattern matching
   - Identify distinctive features
   - Calculate confidence score
   - Determine card type

3. **Classification Phase**
   - Map detected type to output directory
   - Create directory structure if needed
   - Record processing metadata

4. **Output Phase**
   - Organize statements in appropriate folders
   - Generate processing report
   - Log confidence scores and indicators

## Field Mapping Strategy

### AmEx Business Fields
```json
{
  "transaction_date": "MM/DD/YYYY or MMM DD, YYYY",
  "merchant": "text (vendor name)",
  "amount": "currency USD",
  "category": "business classification",
  "reference": "optional alphanumeric ID"
}
```

### Chase Personal Fields
```json
{
  "transaction_date": "MM/DD/YYYY",
  "merchant": "text (vendor name)",
  "location": "optional city/location",
  "amount": "currency USD",
  "transaction_type": "purchase|refund|fee|interest"
}
```

### Visa Fields
```json
{
  "transaction_date": "DD/MM/YYYY or MM/DD/YYYY",
  "merchant": "text (description)",
  "reference": "alphanumeric transaction ID",
  "debit_credit": "D or C indicator",
  "amount": "currency (any)"
}
```

## Handling Format Variations

### Date Format Flexibility
- AmEx: Accepts both "MM/DD/YYYY" and "MMM DD, YYYY"
- Chase: Standardized "MM/DD/YYYY"
- Visa: Supports both "DD/MM/YYYY" and "MM/DD/YYYY"

### Encoding Standards
- All formats: UTF-8 encoding
- AmEx & Visa: CRLF line endings
- Chase: LF line endings

### Delimiter Detection
- AmEx: Comma-delimited CSV
- Chase: Comma-delimited CSV
- Visa: Comma or pipe-delimited

## Confidence Calculation Examples

### High Confidence AmEx (95%+)
- Contains "AMERICAN EXPRESS" header
- Has membership rewards section
- Business category fields present
- Correct date format found

### Medium Confidence Chase (70-90%)
- Contains "CHASE" header
- Has merchant location column
- Correct date format found
- One feature missing

### Low Confidence Visa (40-60%)
- Contains "VISA" header
- Missing balance forward section
- Debit/Credit indicators present
- Format partially matches

## Error Handling

### Missing Files
- Log warning and skip
- Continue processing other statements

### Unreadable Format
- Place in "Unknown" folder
- Log format details for manual review
- Record in processing report

### Encoding Issues
- Attempt UTF-8, then UTF-16
- If all fail, copy to "Unknown" folder
- Note encoding problem in report

## Output Metadata

Each processing run generates:

1. **processing_results.json**
   - Total files processed
   - Count by card type
   - Confidence scores
   - Output locations

2. **organization_summary.txt**
   - Human-readable summary
   - File counts per type
   - Output folder structure
   - Processing statistics

3. **detailed_log.txt** (optional)
   - File-by-file processing details
   - Confidence indicators
   - Feature matches found
   - Any warnings or errors

## Validation Checklist

Before using the organized statements:

- [ ] All AmEx files contain business categories
- [ ] All Chase files have merchant locations
- [ ] All Visa files have Dr/Cr indicators
- [ ] No files misclassified (spot-check Unknown folder)
- [ ] Confidence scores align with file formats
- [ ] All input files accounted for
- [ ] Output directory structure matches specification

## Maintenance Notes

### Regular Updates
- Review Unknown folder monthly
- Reclassify as needed
- Update detection rules if new formats found

### Format Changes
- Monitor for issuer format updates
- Add new patterns to detection rules
- Test with samples before production

### Performance Optimization
- Cache detected formats
- Batch process large statement sets
- Implement parallel processing for 100+ files
