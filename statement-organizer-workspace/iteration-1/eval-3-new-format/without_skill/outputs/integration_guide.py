"""
Integration guide for adding NewBank format to the statement organizer.

This module shows how to:
1. Register the detected format
2. Add parser rules for NewBank
3. Process NewBank statements using the auto-detected mapping
"""

import json
from typing import Dict, Any, List
from format_detection import FormatDetector, FieldType


class BankFormatRegistry:
    """Registry for managing multiple bank formats."""

    def __init__(self):
        """Initialize the registry with existing and new formats."""
        self.formats: Dict[str, Dict[str, Any]] = {}
        self._initialize_standard_formats()

    def _initialize_standard_formats(self):
        """Initialize with known bank formats."""
        # Example: Banco Popular format (existing)
        self.formats["banco-popular"] = {
            "date_column": "Fecha",
            "description_column": "Descripción",
            "debit_column": "Débito",
            "credit_column": "Crédito",
            "balance_column": "Saldo",
            "date_format": "YYYY-MM-DD",
        }

    def register_format(self, bank_name: str, mapping: Dict[str, Any]):
        """
        Register a new bank format.

        Args:
            bank_name: Name of the bank
            mapping: Format mapping dictionary
        """
        self.formats[bank_name.lower()] = mapping
        print(f"Registered format for {bank_name}")

    def get_format(self, bank_name: str) -> Dict[str, Any]:
        """
        Get format for a bank.

        Args:
            bank_name: Name of the bank

        Returns:
            Format mapping or None if not found
        """
        return self.formats.get(bank_name.lower())

    def list_formats(self) -> List[str]:
        """List all registered bank formats."""
        return list(self.formats.keys())


class StatementParser:
    """Parse statements using auto-detected formats."""

    def __init__(self, registry: BankFormatRegistry):
        """
        Initialize parser with format registry.

        Args:
            registry: BankFormatRegistry instance
        """
        self.registry = registry

    def parse_statement(self, filepath: str, bank_name: str) -> List[Dict[str, Any]]:
        """
        Parse a statement using registered or auto-detected format.

        Args:
            filepath: Path to statement CSV
            bank_name: Name of the bank

        Returns:
            List of parsed transactions
        """
        # First try registered format
        format_mapping = self.registry.get_format(bank_name)

        if not format_mapping:
            # Auto-detect format
            print(f"Format not found for {bank_name}, auto-detecting...")
            detector = FormatDetector()
            headers, data_rows = detector.load_csv(filepath)
            columns = detector.analyze_headers(headers, data_rows)
            format_mapping = detector.generate_format_mapping()

            # Register for future use
            self.registry.register_format(bank_name, format_mapping)

        # Parse using the format
        detector = FormatDetector()
        headers, data_rows = detector.load_csv(filepath)
        transactions = detector.parse_transactions(data_rows)

        return transactions


class TransactionNormalizer:
    """Normalize transactions to a standard format."""

    @staticmethod
    def normalize(transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize transaction to standard format.

        Args:
            transaction: Raw transaction from parser

        Returns:
            Normalized transaction
        """
        normalized = {
            "date": transaction.get("transaction_date"),
            "description": transaction.get("merchant", ""),
            "amount": 0.0,
            "type": "unknown",  # "debit" or "credit"
            "balance": transaction.get("balance"),
            "reference": transaction.get("reference_id"),
            "raw": transaction
        }

        # Determine amount and type
        debit = transaction.get("debit_amount", 0.0) or 0.0
        credit = transaction.get("credit_amount", 0.0) or 0.0

        if credit > 0:
            normalized["amount"] = credit
            normalized["type"] = "credit"
        elif debit > 0:
            normalized["amount"] = debit
            normalized["type"] = "debit"

        return normalized


def demo_integration():
    """Demonstrate the full integration workflow."""

    print("=" * 70)
    print("NewBank Format Auto-Detection & Integration Demo")
    print("=" * 70)

    # Step 1: Auto-detect format
    print("\n[Step 1] Auto-detecting NewBank format...")
    detector = FormatDetector()
    filepath = "/sessions/amazing-sharp-clarke/mnt/rex/statement-organizer-workspace/iteration-1/eval-3-new-format/test_statements/Personal/You/Banks/NewBank-March-2026.csv"

    headers, data_rows = detector.load_csv(filepath)
    columns = detector.analyze_headers(headers, data_rows)

    print(f"Detected columns:")
    for col in columns:
        if col.field_type != FieldType.UNKNOWN:
            print(f"  - {col.name:25} -> {col.field_type.value:15} (confidence: {col.confidence:.2f})")

    # Step 2: Generate mapping
    print("\n[Step 2] Generating format mapping...")
    mapping = detector.generate_format_mapping()
    print(f"Overall detection confidence: {mapping['detection_confidence']:.2f}")
    print(f"Required fields: {', '.join(mapping['required_fields'])}")

    # Step 3: Register format
    print("\n[Step 3] Registering format in bank registry...")
    registry = BankFormatRegistry()
    registry.register_format("NewBank", mapping)
    print(f"Available formats: {', '.join(registry.list_formats())}")

    # Step 4: Parse transactions
    print("\n[Step 4] Parsing transactions...")
    parser = StatementParser(registry)
    transactions = parser.parse_statement(filepath, "NewBank")
    print(f"Parsed {len(transactions)} transactions")

    # Step 5: Normalize transactions
    print("\n[Step 5] Normalizing transactions...")
    normalizer = TransactionNormalizer()
    normalized = [normalizer.normalize(tx) for tx in transactions]

    print("\nFirst 3 normalized transactions:")
    for tx in normalized[:3]:
        print(f"  Date: {tx['date']}")
        print(f"    Description: {tx['description']}")
        print(f"    Amount: ${tx['amount']:.2f} ({tx['type']})")
        print(f"    Balance: ${tx['balance']}")
        print()

    # Step 6: Save mapping
    print("[Step 6] Saving mapping to file...")
    with open("/sessions/amazing-sharp-clarke/mnt/rex/statement-organizer-workspace/iteration-1/eval-3-new-format/without_skill/outputs/sample_mapping.json", "w") as f:
        json.dump(mapping, f, indent=2)
    print("Mapping saved to sample_mapping.json")

    return {
        "columns": columns,
        "mapping": mapping,
        "transactions": transactions,
        "normalized": normalized
    }


if __name__ == "__main__":
    results = demo_integration()
    print("\n" + "=" * 70)
    print(f"Integration complete! Processed {len(results['transactions'])} transactions")
    print("=" * 70)
