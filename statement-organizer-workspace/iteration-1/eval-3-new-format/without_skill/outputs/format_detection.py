"""
Auto-detect CSV statement format and create mappings for new banks.

This module provides functionality to:
1. Detect column headers in CSV files
2. Infer transaction field types based on content analysis
3. Generate format mappings for future parsing
4. Validate detected formats
"""

import csv
import re
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class FieldType(Enum):
    """Possible field types in bank statements."""
    DATE = "date"
    DESCRIPTION = "description"
    AMOUNT = "amount"
    DEBIT = "debit"
    CREDIT = "credit"
    BALANCE = "balance"
    REFERENCE = "reference"
    UNKNOWN = "unknown"


@dataclass
class ColumnInfo:
    """Information about a detected column."""
    name: str
    index: int
    field_type: FieldType
    confidence: float
    sample_values: List[str]


class FormatDetector:
    """Detect and analyze bank statement CSV formats."""

    # Patterns for detecting field types
    DATE_PATTERNS = [
        r'^\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'^\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'^\d{1,2}-\w{3}-\d{4}',  # DD-MMM-YYYY
    ]

    AMOUNT_PATTERNS = [
        r'^-?\d+\.?\d*$',  # Plain number
        r'^\$?-?\d+\.?\d*$',  # With optional $
        r'^-?\d{1,3}(,\d{3})*\.?\d*$',  # With thousands separator
    ]

    DEBIT_KEYWORDS = [
        'debit', 'withdrawal', 'payment', 'charge', 'expense',
        'out', 'spend', 'cost'
    ]

    CREDIT_KEYWORDS = [
        'credit', 'deposit', 'transfer in', 'income', 'receipt',
        'in', 'gain', 'deposit'
    ]

    DATE_KEYWORDS = [
        'date', 'fecha', 'transaction date', 'trans date', 'posting date'
    ]

    DESCRIPTION_KEYWORDS = [
        'description', 'descripción', 'merchant', 'payee', 'details',
        'memo', 'narrative', 'reference'
    ]

    BALANCE_KEYWORDS = [
        'balance', 'saldo', 'running balance', 'account balance', 'available'
    ]

    def __init__(self):
        """Initialize the detector."""
        self.columns: List[ColumnInfo] = []
        self.raw_data: List[List[str]] = []

    def load_csv(self, filepath: str) -> Tuple[List[str], List[List[str]]]:
        """
        Load a CSV file and return headers and data rows.

        Args:
            filepath: Path to the CSV file

        Returns:
            Tuple of (headers, data_rows)
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            data_rows = list(reader)

        self.raw_data = data_rows
        return headers, data_rows

    def detect_field_type(self, column_name: str, column_values: List[str],
                         index: int) -> Tuple[FieldType, float]:
        """
        Detect the field type of a column based on header name and values.

        Args:
            column_name: The column header
            column_values: Sample values from the column
            index: Column index

        Returns:
            Tuple of (FieldType, confidence_score)
        """
        lower_name = column_name.lower().strip()

        # Check header-based clues first
        for keyword in self.DATE_KEYWORDS:
            if keyword in lower_name:
                return FieldType.DATE, 0.9

        for keyword in self.DESCRIPTION_KEYWORDS:
            if keyword in lower_name:
                return FieldType.DESCRIPTION, 0.9

        for keyword in self.BALANCE_KEYWORDS:
            if keyword in lower_name:
                return FieldType.BALANCE, 0.9

        for keyword in self.DEBIT_KEYWORDS:
            if keyword in lower_name:
                return FieldType.DEBIT, 0.85

        for keyword in self.CREDIT_KEYWORDS:
            if keyword in lower_name:
                return FieldType.CREDIT, 0.85

        if 'ref' in lower_name or 'id' in lower_name:
            return FieldType.REFERENCE, 0.8

        # Content-based detection
        non_empty_values = [v for v in column_values if v.strip()]
        if not non_empty_values:
            return FieldType.UNKNOWN, 0.0

        # Check if all values are dates
        date_matches = sum(1 for v in non_empty_values
                          if any(re.match(p, v.strip()) for p in self.DATE_PATTERNS))
        if date_matches / len(non_empty_values) > 0.8:
            return FieldType.DATE, 0.8

        # Check if all values are amounts
        amount_matches = sum(1 for v in non_empty_values
                            if any(re.match(p, v.strip()) for p in self.AMOUNT_PATTERNS))
        if amount_matches / len(non_empty_values) > 0.8:
            # Determine if debit or credit or generic amount
            if 'debit' in lower_name or 'withdrawal' in lower_name or 'out' in lower_name:
                return FieldType.DEBIT, 0.85
            elif 'credit' in lower_name or 'deposit' in lower_name or 'in' in lower_name:
                return FieldType.CREDIT, 0.85
            else:
                return FieldType.AMOUNT, 0.7

        # Check if it's likely a reference/ID
        if all(re.match(r'^[A-Z0-9\-]+$', v.strip()) for v in non_empty_values[:min(3, len(non_empty_values))]):
            return FieldType.REFERENCE, 0.7

        # Default to description for text columns
        if any(len(v) > 20 for v in non_empty_values):
            return FieldType.DESCRIPTION, 0.6

        return FieldType.UNKNOWN, 0.5

    def analyze_headers(self, headers: List[str], data_rows: List[List[str]]) -> List[ColumnInfo]:
        """
        Analyze column headers and detect field types.

        Args:
            headers: List of column headers
            data_rows: Sample data rows

        Returns:
            List of ColumnInfo objects
        """
        columns = []

        for idx, header in enumerate(headers):
            # Get sample values from this column
            sample_values = [
                row[idx] if idx < len(row) else ""
                for row in data_rows[:min(5, len(data_rows))]
            ]

            field_type, confidence = self.detect_field_type(
                header, sample_values, idx
            )

            col_info = ColumnInfo(
                name=header,
                index=idx,
                field_type=field_type,
                confidence=confidence,
                sample_values=sample_values
            )
            columns.append(col_info)

        self.columns = columns
        return columns

    def generate_format_mapping(self) -> Dict[str, Any]:
        """
        Generate a format mapping dictionary from detected columns.

        Returns:
            Dictionary with format configuration
        """
        mapping = {
            "format_name": "auto_detected",
            "fields": {},
            "required_fields": [],
            "validation_rules": {},
            "detection_confidence": 0.0
        }

        total_confidence = 0.0
        valid_fields = 0

        for col in self.columns:
            if col.field_type != FieldType.UNKNOWN:
                mapping["fields"][col.name] = {
                    "field_type": col.field_type.value,
                    "index": col.index,
                    "confidence": col.confidence,
                    "sample_values": col.sample_values[:3]
                }

                total_confidence += col.confidence
                valid_fields += 1

                # Mark certain fields as required
                if col.field_type in [FieldType.DATE, FieldType.DESCRIPTION, FieldType.AMOUNT]:
                    mapping["required_fields"].append(col.name)

        if valid_fields > 0:
            mapping["detection_confidence"] = total_confidence / valid_fields

        # Add validation rules
        for col in self.columns:
            if col.field_type == FieldType.DATE:
                mapping["validation_rules"][col.name] = {
                    "type": "date",
                    "formats": ["YYYY-MM-DD", "MM/DD/YYYY", "DD-MMM-YYYY"]
                }
            elif col.field_type in [FieldType.AMOUNT, FieldType.DEBIT, FieldType.CREDIT, FieldType.BALANCE]:
                mapping["validation_rules"][col.name] = {
                    "type": "numeric",
                    "pattern": r"^-?\d+\.?\d*$"
                }

        return mapping

    def parse_transactions(self, data_rows: List[List[str]]) -> List[Dict[str, Any]]:
        """
        Parse CSV rows into transaction dictionaries using detected format.

        Args:
            data_rows: Raw CSV data rows

        Returns:
            List of parsed transaction dictionaries
        """
        transactions = []

        for row in data_rows:
            transaction = {}
            for col in self.columns:
                if col.index < len(row):
                    value = row[col.index].strip()

                    # Convert based on detected type
                    if col.field_type == FieldType.DATE:
                        transaction["transaction_date"] = value
                    elif col.field_type == FieldType.DESCRIPTION:
                        transaction["merchant"] = value
                    elif col.field_type == FieldType.DEBIT:
                        try:
                            amount = float(value) if value else 0.0
                            transaction["debit_amount"] = abs(amount)
                        except ValueError:
                            transaction["debit_amount"] = None
                    elif col.field_type == FieldType.CREDIT:
                        try:
                            amount = float(value) if value else 0.0
                            transaction["credit_amount"] = abs(amount)
                        except ValueError:
                            transaction["credit_amount"] = None
                    elif col.field_type == FieldType.AMOUNT:
                        try:
                            amount = float(value) if value else 0.0
                            # Infer if debit or credit from negative sign
                            if amount < 0:
                                transaction["debit_amount"] = abs(amount)
                            else:
                                transaction["credit_amount"] = abs(amount)
                        except ValueError:
                            pass
                    elif col.field_type == FieldType.BALANCE:
                        try:
                            transaction["balance"] = float(value) if value else None
                        except ValueError:
                            transaction["balance"] = None
                    elif col.field_type == FieldType.REFERENCE:
                        transaction["reference_id"] = value

            if transaction:
                transactions.append(transaction)

        return transactions


def main():
    """Example usage of format detector."""
    detector = FormatDetector()

    # Example: detect format from NewBank statement
    test_file = "/sessions/amazing-sharp-clarke/mnt/rex/statement-organizer-workspace/iteration-1/eval-3-new-format/test_statements/Personal/You/Banks/NewBank-March-2026.csv"

    headers, data_rows = detector.load_csv(test_file)
    print(f"Detected {len(headers)} columns: {headers}\n")

    columns = detector.analyze_headers(headers, data_rows)

    print("Column Analysis:")
    for col in columns:
        print(f"  {col.name:25} -> {col.field_type.value:15} (confidence: {col.confidence:.2f})")

    print("\nFormat Mapping:")
    mapping = detector.generate_format_mapping()
    print(f"  Overall confidence: {mapping['detection_confidence']:.2f}")
    print(f"  Required fields: {mapping['required_fields']}")

    print("\nParsed Transactions (first 3):")
    transactions = detector.parse_transactions(data_rows)
    for tx in transactions[:3]:
        print(f"  {tx}")

    return detector, mapping, transactions


if __name__ == "__main__":
    main()
