#!/usr/bin/env python3
"""
Statement Organizer - Main Processing Script
Handles statement parsing, format learning, FreshBooks sync, and reporting
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import re
from difflib import SequenceMatcher

# Setup logging
log_dir = Path("Statements/Logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f"statement-processing-{datetime.now().strftime('%Y-%m-%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class StatementProcessor:
    """Main statement processing engine"""

    def __init__(self, statements_dir: str = "Statements"):
        self.statements_dir = Path(statements_dir)
        self.formats_file = self.statements_dir / ".statement-formats.json"
        self.freshbooks_config_file = self.statements_dir / ".freshbooks-config.json"
        self.logs_dir = self.statements_dir / "Logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.formats = self._load_formats()
        self.freshbooks_config = self._load_freshbooks_config()

    def _load_formats(self) -> Dict:
        """Load learned statement formats"""
        if self.formats_file.exists():
            with open(self.formats_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_formats(self):
        """Save updated formats to disk"""
        with open(self.formats_file, 'w') as f:
            json.dump(self.formats, f, indent=2)

    def _load_freshbooks_config(self) -> Dict:
        """Load FreshBooks configuration"""
        config = {}

        # Try env var first
        token = os.environ.get('FRESHBOOKS_API_TOKEN')
        if token:
            config['api_token'] = token

        # Try config file second
        if self.freshbooks_config_file.exists():
            with open(self.freshbooks_config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)

        return config

    def detect_bank(self, file_path: str) -> Optional[str]:
        """Detect bank from filename and first row of CSV"""
        filename = Path(file_path).name.lower()

        # Filename-based detection
        if 'dart' in filename:
            return 'Dart Bank'
        if 'banco' in filename or 'popular' in filename:
            return 'Banco Popular'

        # CSV header-based detection
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    header_str = ' '.join(reader.fieldnames).lower()
                    if 'dart' in header_str:
                        return 'Dart Bank'
                    if 'banco' in header_str:
                        return 'Banco Popular'
        except Exception as e:
            logger.error(f"Error reading file for bank detection: {e}")

        return None

    def learn_format(self, file_path: str, bank_name: str) -> Dict:
        """Learn the format of a statement"""
        logger.info(f"Learning format for {bank_name}: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames

                if not fieldnames:
                    logger.error(f"No headers found in {file_path}")
                    return {}

                # Auto-detect common column patterns
                mapping = self._auto_detect_columns(fieldnames, bank_name)

                if not mapping:
                    logger.warning(f"Could not auto-detect format for {bank_name}")
                    # Prompt user to identify columns
                    mapping = self._interactive_format_setup(fieldnames, bank_name)

                self.formats[bank_name] = mapping
                self._save_formats()
                logger.info(f"Format learned and saved for {bank_name}")
                return mapping

        except Exception as e:
            logger.error(f"Error learning format: {e}")
            return {}

    def _auto_detect_columns(self, fieldnames: List[str], bank_name: str) -> Dict:
        """Auto-detect column mappings from field names"""
        fields_lower = [f.lower() for f in fieldnames]
        field_map = {f.lower(): f for f in fieldnames}

        mapping = {
            'file_pattern': f'*{bank_name}*',
            'detected_fields': fieldnames
        }

        # Look for date columns
        date_patterns = ['fecha', 'date', 'transaction date', 'posted date']
        for pattern in date_patterns:
            for f in fields_lower:
                if pattern in f:
                    mapping['date_column'] = field_map[f]
                    break

        # Look for amount columns
        amount_patterns = ['monto', 'amount', 'total', 'valor']
        for pattern in amount_patterns:
            for f in fields_lower:
                if pattern in f and 'column' not in f:
                    mapping['amount_column'] = field_map[f]
                    break

        # Look for merchant/description
        merchant_patterns = ['merchant', 'descripción', 'description', 'vendor', 'payee']
        for pattern in merchant_patterns:
            for f in fields_lower:
                if pattern in f:
                    mapping['merchant_column'] = field_map[f]
                    break

        # Look for debit/credit columns (common in bank statements)
        for f in fields_lower:
            if 'debit' in f or 'débito' in f:
                mapping['debit_amount_column'] = field_map[f]
            if 'credit' in f or 'crédito' in f:
                mapping['credit_amount_column'] = field_map[f]

        # Validate that we found the essential columns
        if 'date_column' in mapping and 'amount_column' in mapping:
            logger.info(f"Auto-detected format for {bank_name}")
            return mapping

        return {}

    def _interactive_format_setup(self, fieldnames: List[str], bank_name: str) -> Dict:
        """Interactive format setup (prompts user to identify columns)"""
        logger.warning(f"Could not auto-detect format. Manual identification needed.")
        mapping = {'file_pattern': f'*{bank_name}*'}

        # For now, return empty - in practice, Claude will ask the user
        logger.info("Please identify which columns contain: date, amount, merchant")
        return mapping

    def parse_statement(self, file_path: str, bank_name: str) -> List[Dict]:
        """Parse a statement CSV using the learned format"""
        format_info = self.formats.get(bank_name)

        if not format_info:
            logger.info(f"Format not found for {bank_name}, attempting to learn it...")
            format_info = self.learn_format(file_path, bank_name)

        if not format_info or 'date_column' not in format_info:
            logger.error(f"Cannot parse {file_path}: format information incomplete")
            return []

        transactions = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    transaction = self._extract_transaction(row, format_info)
                    if transaction:
                        transactions.append(transaction)

            logger.info(f"Parsed {len(transactions)} transactions from {file_path}")
        except Exception as e:
            logger.error(f"Error parsing statement: {e}")

        return transactions

    def _extract_transaction(self, row: Dict, format_info: Dict) -> Optional[Dict]:
        """Extract relevant fields from a transaction row"""
        try:
            date_col = format_info.get('date_column')
            amount_col = format_info.get('amount_column')
            merchant_col = format_info.get('merchant_column')

            if not all([date_col, amount_col]):
                return None

            # Get amount (try debit/credit columns if available)
            amount = None
            if amount_col in row:
                try:
                    amount = float(row[amount_col].replace(',', '').replace('$', ''))
                except (ValueError, AttributeError):
                    return None
            elif 'debit_amount_column' in format_info or 'credit_amount_column' in format_info:
                debit_col = format_info.get('debit_amount_column')
                credit_col = format_info.get('credit_amount_column')

                if debit_col and row.get(debit_col):
                    try:
                        amount = -float(row[debit_col].replace(',', '').replace('$', ''))
                    except ValueError:
                        pass
                elif credit_col and row.get(credit_col):
                    try:
                        amount = float(row[credit_col].replace(',', '').replace('$', ''))
                    except ValueError:
                        pass

            if amount is None:
                return None

            return {
                'date': row.get(date_col, ''),
                'amount': amount,
                'merchant': row.get(merchant_col, ''),
                'raw_row': row
            }
        except Exception as e:
            logger.debug(f"Error extracting transaction: {e}")
            return None

    def match_with_freshbooks(self, transactions: List[Dict], statement_date: str) -> Dict:
        """Match transactions with FreshBooks invoices"""

        if not self.freshbooks_config.get('api_token'):
            logger.warning("FreshBooks API token not configured. Skipping sync.")
            return {'matched': [], 'ambiguous': [], 'unmatched': []}

        # TODO: Implement FreshBooks API integration
        # This requires the FreshBooks Python SDK or direct API calls
        logger.info(f"FreshBooks integration placeholder - {len(transactions)} transactions ready for matching")

        results = {
            'matched': [],
            'ambiguous': [],
            'unmatched': list(transactions)
        }

        return results

    def generate_report(self, matches: Dict, statement_date: str) -> str:
        """Generate CSV report of matches"""
        report_path = self.logs_dir / f"freshbooks-matches-{datetime.now().strftime('%Y-%m-%d')}.csv"

        try:
            with open(report_path, 'w', newline='') as f:
                writer = csv.writer(f)

                # Write matched transactions
                writer.writerow(['MATCHED INVOICES - AUTO-MARKED PAID'])
                writer.writerow(['Date', 'Amount', 'Merchant', 'Invoice ID', 'Status'])
                for match in matches.get('matched', []):
                    writer.writerow([
                        match.get('date'),
                        match.get('amount'),
                        match.get('merchant'),
                        match.get('invoice_id', 'N/A'),
                        'Marked Paid'
                    ])

                writer.writerow([])  # Blank row

                # Write ambiguous matches
                writer.writerow(['AMBIGUOUS MATCHES - NEEDS REVIEW'])
                writer.writerow(['Date', 'Amount', 'Merchant', 'Possible Invoices', 'Recommendation'])
                for match in matches.get('ambiguous', []):
                    writer.writerow([
                        match.get('date'),
                        match.get('amount'),
                        match.get('merchant'),
                        ' | '.join(match.get('possible_invoices', [])),
                        'Review and confirm'
                    ])

                writer.writerow([])  # Blank row

                # Write unmatched transactions
                writer.writerow(['UNMATCHED TRANSACTIONS - INVESTIGATE'])
                writer.writerow(['Date', 'Amount', 'Merchant', 'Action'])
                for match in matches.get('unmatched', []):
                    writer.writerow([
                        match.get('date'),
                        match.get('amount'),
                        match.get('merchant'),
                        'No matching invoice found'
                    ])

            logger.info(f"Report generated: {report_path}")
            return str(report_path)

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return ""


def main():
    """Main entry point"""
    processor = StatementProcessor()
    logger.info("Statement Organizer ready")
    return processor


if __name__ == '__main__':
    main()
