#!/usr/bin/env python3
"""
Banco Popular CSV Statement Parser
Parses Banco Popular bank statements and extracts structured transaction data.
"""

import csv
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import json


@dataclass
class Transaction:
    """Represents a single transaction from the statement."""
    date: str
    description: str
    reference: str
    deposit_amount: float
    withdrawal_amount: float
    balance: float
    transaction_type: str
    category: str

    def to_dict(self):
        return asdict(self)


class BancoPopularFormatDetector:
    """Detects if a CSV file is in Banco Popular format."""

    BANCO_POPULAR_SIGNATURE = {
        'required_columns': ['Fecha', 'Descripcion', 'Referencia', 'Depositos', 'Retiros', 'Saldo'],
        'expected_patterns': [
            r'Banco Popular',
            r'Deposito Directa',
            r'Transferencia',
            r'Compra Tarjeta Debito',
            r'Cajero Automatico',
        ],
        'date_format': '%Y-%m-%d',
    }

    @staticmethod
    def detect_format(file_path: str) -> Tuple[bool, Dict]:
        """
        Detect if file is Banco Popular format.

        Returns:
            Tuple of (is_banco_popular, detection_details)
        """
        detection_details = {
            'is_banco_popular': False,
            'confidence': 0,
            'detected_columns': [],
            'missing_columns': [],
            'issues': []
        }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read first few lines to detect format
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    detection_details['issues'].append('No header row detected')
                    return False, detection_details

                detected_columns = list(reader.fieldnames)
                detection_details['detected_columns'] = detected_columns

                # Check required columns
                required = BancoPopularFormatDetector.BANCO_POPULAR_SIGNATURE['required_columns']
                missing = [col for col in required if col not in detected_columns]

                if missing:
                    detection_details['missing_columns'] = missing
                    detection_details['issues'].append(f'Missing columns: {missing}')
                else:
                    detection_details['confidence'] += 40

                # Check for pattern signatures in data
                f.seek(0)
                reader = csv.DictReader(f)
                pattern_matches = 0
                total_rows = 0

                for row in reader:
                    total_rows += 1
                    if total_rows > 20:  # Check first 20 rows
                        break

                    description = row.get('Descripcion', '')
                    for pattern in BancoPopularFormatDetector.BANCO_POPULAR_SIGNATURE['expected_patterns']:
                        if re.search(pattern, description, re.IGNORECASE):
                            pattern_matches += 1

                if total_rows > 0:
                    pattern_confidence = (pattern_matches / total_rows) * 30
                    detection_details['confidence'] += pattern_confidence

                # Check date format
                f.seek(0)
                reader = csv.DictReader(f)
                date_valid_count = 0
                for i, row in enumerate(reader):
                    if i > 10:
                        break
                    try:
                        datetime.strptime(row.get('Fecha', ''), '%Y-%m-%d')
                        date_valid_count += 1
                    except ValueError:
                        pass

                if date_valid_count > 0:
                    detection_details['confidence'] += 30

                # Final determination
                detection_details['is_banco_popular'] = (
                    not missing and detection_details['confidence'] >= 60
                )

        except Exception as e:
            detection_details['issues'].append(f'Error reading file: {str(e)}')

        return detection_details['is_banco_popular'], detection_details


class BancoPopularParser:
    """Parses Banco Popular CSV statements."""

    TRANSACTION_CATEGORIES = {
        'Deposito Directa': 'Income',
        'Deposito Cheque': 'Income',
        'Transferencia Recibida': 'Income',
        'Interes': 'Income',
        'Compra Tarjeta Debito': 'Expense',
        'Transferencia': 'Expense',
        'Transferencia Enviada': 'Expense',
        'Retiro Cajero': 'Expense',
        'Pago Factura': 'Expense',
        'Comisión': 'Fee',
        'Cargo': 'Fee',
    }

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.transactions: List[Transaction] = []
        self.parser_metadata = {
            'file_path': file_path,
            'bank': 'Banco Popular',
            'total_transactions': 0,
            'date_range': None,
            'currency': 'DOP',  # Dominican Pesos (typical for Banco Popular)
            'encoding': 'utf-8'
        }

    def categorize_transaction(self, description: str) -> str:
        """Categorize transaction based on description."""
        for keyword, category in self.TRANSACTION_CATEGORIES.items():
            if keyword.lower() in description.lower():
                return category
        return 'Other'

    def determine_transaction_type(self, description: str, deposit: float, withdrawal: float) -> str:
        """Determine specific transaction type."""
        if deposit > 0:
            if 'Deposito Directa' in description:
                return 'Direct Deposit'
            elif 'Deposito Cheque' in description:
                return 'Check Deposit'
            elif 'Transferencia Recibida' in description:
                return 'Transfer In'
            elif 'Interes' in description:
                return 'Interest'
            else:
                return 'Deposit'
        elif withdrawal > 0:
            if 'Compra Tarjeta Debito' in description:
                return 'Debit Card Purchase'
            elif 'Transferencia Enviada' in description or 'Transferencia a' in description:
                return 'Transfer Out'
            elif 'Retiro Cajero' in description:
                return 'ATM Withdrawal'
            elif 'Pago Factura' in description:
                return 'Bill Payment'
            elif 'Comisión' in description or 'Cargo' in description:
                return 'Fee'
            else:
                return 'Withdrawal'
        else:
            return 'Balance'

    def parse(self) -> List[Transaction]:
        """Parse the CSV file and return list of transactions."""
        transactions = []

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        # Extract and clean data
                        fecha = row.get('Fecha', '').strip()
                        descripcion = row.get('Descripcion', '').strip()
                        referencia = row.get('Referencia', '').strip()

                        # Handle numeric fields with missing values
                        depositos_str = row.get('Depositos', '').strip()
                        retiros_str = row.get('Retiros', '').strip()
                        saldo_str = row.get('Saldo', '').strip()

                        # Convert to float, treating '-' and empty as 0
                        depositos = self._parse_amount(depositos_str)
                        retiros = self._parse_amount(retiros_str)
                        saldo = self._parse_amount(saldo_str)

                        # Skip rows that are clearly not transactions (headers, totals, etc.)
                        if not fecha or fecha.lower() in ['fecha', 'date']:
                            continue

                        # Validate date format
                        try:
                            datetime.strptime(fecha, '%Y-%m-%d')
                        except ValueError:
                            continue

                        # Determine transaction type and category
                        tx_type = self.determine_transaction_type(descripcion, depositos, retiros)
                        category = self.categorize_transaction(descripcion)

                        transaction = Transaction(
                            date=fecha,
                            description=descripcion,
                            reference=referencia,
                            deposit_amount=depositos,
                            withdrawal_amount=retiros,
                            balance=saldo,
                            transaction_type=tx_type,
                            category=category
                        )

                        transactions.append(transaction)

                    except Exception as e:
                        print(f"Warning: Could not parse row: {row}. Error: {e}")
                        continue

            self.transactions = transactions
            self.parser_metadata['total_transactions'] = len(transactions)

            if transactions:
                dates = [datetime.strptime(t.date, '%Y-%m-%d') for t in transactions]
                self.parser_metadata['date_range'] = {
                    'start': min(dates).isoformat(),
                    'end': max(dates).isoformat()
                }

        except Exception as e:
            print(f"Error parsing file: {e}")

        return transactions

    @staticmethod
    def _parse_amount(value: str) -> float:
        """Parse amount string, handling various formats."""
        if not value or value.strip() in ['-', '']:
            return 0.0

        # Remove common separators and convert to float
        value = value.strip()
        value = value.replace(',', '').replace('DOP', '').strip()

        try:
            return float(value)
        except ValueError:
            return 0.0

    def get_summary_stats(self) -> Dict:
        """Calculate summary statistics from transactions."""
        if not self.transactions:
            return {}

        total_deposits = sum(t.deposit_amount for t in self.transactions)
        total_withdrawals = sum(t.withdrawal_amount for t in self.transactions)
        net_change = total_deposits - total_withdrawals

        # Categorize transactions
        by_category = {}
        by_type = {}

        for tx in self.transactions:
            # By category
            if tx.category not in by_category:
                by_category[tx.category] = {'count': 0, 'amount': 0}
            by_category[tx.category]['count'] += 1
            by_category[tx.category]['amount'] += (tx.deposit_amount - tx.withdrawal_amount)

            # By type
            if tx.transaction_type not in by_type:
                by_type[tx.transaction_type] = {'count': 0, 'amount': 0}
            by_type[tx.transaction_type]['count'] += 1
            by_type[tx.transaction_type]['amount'] += (tx.deposit_amount - tx.withdrawal_amount)

        return {
            'total_transactions': len(self.transactions),
            'total_deposits': total_deposits,
            'total_withdrawals': total_withdrawals,
            'net_change': net_change,
            'by_category': by_category,
            'by_type': by_type,
            'metadata': self.parser_metadata
        }


def main():
    """Main function to demonstrate parser usage."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_banco_popular.py <input_file> [output_file]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    # Detect format
    print(f"Detecting format for: {input_file}")
    is_bp, details = BancoPopularFormatDetector.detect_format(input_file)
    print(f"  Format detected: {is_bp}")
    print(f"  Confidence: {details['confidence']:.1f}%")
    print(f"  Columns: {details['detected_columns']}")

    if not is_bp:
        print("WARNING: File does not appear to be Banco Popular format")
        return

    # Parse file
    print(f"\nParsing {input_file}...")
    parser = BancoPopularParser(input_file)
    transactions = parser.parse()

    print(f"  Found {len(transactions)} transactions")

    # Get statistics
    stats = parser.get_summary_stats()
    print(f"\nSummary Statistics:")
    print(f"  Total Deposits: DOP {stats['total_deposits']:.2f}")
    print(f"  Total Withdrawals: DOP {stats['total_withdrawals']:.2f}")
    print(f"  Net Change: DOP {stats['net_change']:.2f}")

    # Output results
    if output_file:
        with open(output_file, 'w') as f:
            json.dump([tx.to_dict() for tx in transactions], f, indent=2)
        print(f"\nTransactions saved to: {output_file}")

    return parser, transactions, stats


if __name__ == '__main__':
    main()
