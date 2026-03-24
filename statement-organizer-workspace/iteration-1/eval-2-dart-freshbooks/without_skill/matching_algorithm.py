"""
Dart Bank Statement to FreshBooks Invoice Matching Algorithm

This module implements a multi-strategy matching algorithm to reconcile bank
transactions with unpaid FreshBooks invoices. The algorithm uses amount matching,
merchant name matching, and date proximity scoring to identify which transactions
correspond to which invoices.
"""

import csv
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class BankTransaction:
    """Represents a Dart Bank statement transaction"""
    date: datetime
    merchant: str
    amount: float
    reference: str
    transaction_id: str

    def __repr__(self):
        return f"BankTxn({self.transaction_id}, {self.merchant}, ${self.amount:.2f}, {self.date.date()})"


@dataclass
class FreshBooksInvoice:
    """Represents a FreshBooks invoice"""
    invoice_id: str
    client_name: str
    amount: float
    status: str
    date: datetime
    notes: str

    def __repr__(self):
        return f"Invoice({self.invoice_id}, {self.client_name}, ${self.amount:.2f})"


@dataclass
class MatchResult:
    """Result of a match attempt between transaction and invoice"""
    transaction: BankTransaction
    invoice: Optional[FreshBooksInvoice]
    match_score: float
    match_type: str  # "exact", "probable", "ambiguous", "no_match"
    notes: str


class DartFreshBooksMatchEngine:
    """
    Multi-strategy matching engine for bank transactions and invoices.

    Matching strategy (in order of priority):
    1. Amount Match: Transaction amount == Invoice amount (exact)
    2. Merchant Name Match: Extract invoice ID from merchant name
    3. Date Proximity: Check if transaction date is within 30 days of invoice date
    4. Fuzzy Match: Check for partial name matches with tolerance
    """

    def __init__(self, amount_tolerance: float = 0.01,
                 date_window_days: int = 30,
                 fuzzy_match_threshold: float = 0.85):
        """
        Initialize the matching engine.

        Args:
            amount_tolerance: Tolerance in dollars for amount matching
            date_window_days: Days to look forward/back for date proximity
            fuzzy_match_threshold: Similarity threshold (0-1) for fuzzy matching
        """
        self.amount_tolerance = amount_tolerance
        self.date_window_days = date_window_days
        self.fuzzy_match_threshold = fuzzy_match_threshold
        self.transactions: List[BankTransaction] = []
        self.invoices: List[FreshBooksInvoice] = []
        self.matches: List[MatchResult] = []

    def load_bank_statement(self, csv_file: str):
        """Load transactions from Dart Bank CSV statement"""
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                txn = BankTransaction(
                    date=datetime.strptime(row['Date'], '%Y-%m-%d'),
                    merchant=row['Merchant'].strip(),
                    amount=float(row['Amount']),
                    reference=row['Reference'].strip(),
                    transaction_id=row['TransactionID'].strip()
                )
                self.transactions.append(txn)

    def load_invoices(self, csv_file: str):
        """Load invoices from FreshBooks CSV export"""
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                invoice = FreshBooksInvoice(
                    invoice_id=row['InvoiceID'].strip(),
                    client_name=row['ClientName'].strip(),
                    amount=float(row['Amount']),
                    status=row['Status'].strip(),
                    date=datetime.strptime(row['Date'], '%Y-%m-%d'),
                    notes=row['Notes'].strip() if 'Notes' in row else ''
                )
                self.invoices.append(invoice)

    def extract_invoice_id_from_reference(self, reference: str) -> Optional[str]:
        """
        Extract invoice ID patterns from transaction reference field.

        Looks for common patterns:
        - INV-XXXX-XXX
        - Invoice XXXX
        - REF-XXXX-XXX
        - XXXX-XXX (numeric patterns)
        """
        reference_upper = reference.upper()

        # Pattern 1: Look for "INV-2026-" or "INV-" prefix
        if 'INV-' in reference_upper:
            # Extract the full invoice ID
            parts = reference_upper.split()
            for part in parts:
                if 'INV-' in part:
                    # Return in standardized format
                    return part.replace(',', '')

        # Pattern 2: Look for invoice numbers after "Invoice" keyword
        if 'INVOICE' in reference_upper:
            parts = reference.split()
            for i, part in enumerate(parts):
                if part.upper() == 'INVOICE' and i + 1 < len(parts):
                    potential_id = parts[i + 1].replace(',', '')
                    return f"INV-{potential_id}" if potential_id.isdigit() else potential_id

        # Pattern 3: Look for REF- pattern
        if 'REF-' in reference_upper:
            parts = reference_upper.split()
            for part in parts:
                if 'REF-' in part:
                    return part.replace(',', '')

        # Pattern 4: Check for numeric patterns that match invoice IDs
        parts = reference.split()
        for part in parts:
            cleaned = part.replace(',', '').upper()
            if cleaned.isdigit() and len(cleaned) >= 3:
                return f"INV-{cleaned}"

        return None

    def extract_merchant_code(self, merchant: str) -> Optional[str]:
        """
        Extract Portal42 client identifier from merchant name.

        Example: "Portal42-Acme Corp" -> "Acme Corp"
        """
        if 'Portal42-' in merchant or 'Portal42 ' in merchant:
            # Remove the Portal42 prefix
            return merchant.replace('Portal42-', '').replace('Portal42 ', '').strip()
        return None

    def fuzzy_match_score(self, str1: str, str2: str) -> float:
        """
        Calculate string similarity score (0-1).

        Simple implementation using Levenshtein-like approach.
        Returns 1.0 for exact match, lower for partial matches.
        """
        str1_lower = str1.lower().strip()
        str2_lower = str2.lower().strip()

        # Exact match
        if str1_lower == str2_lower:
            return 1.0

        # Check if one contains the other
        if str1_lower in str2_lower or str2_lower in str1_lower:
            # Partial match - score based on overlap ratio
            longer = max(len(str1_lower), len(str2_lower))
            shorter = min(len(str1_lower), len(str2_lower))
            return shorter / longer if longer > 0 else 0

        # No match
        return 0

    def score_match(self, transaction: BankTransaction,
                   invoice: FreshBooksInvoice) -> Tuple[float, Dict]:
        """
        Calculate match score between transaction and invoice.

        Returns:
            Tuple of (score: float, details: dict)

        Score breakdown:
            - Amount match: 0-40 points (exact = 40, within tolerance = 30)
            - Invoice ID match: 50 points (if reference contains invoice ID)
            - Client name match: 0-20 points (fuzzy match)
            - Date proximity: 0-10 points (invoice date <= transaction date <= invoice date + 30 days)
        """
        details = {}
        score = 0

        # 1. Amount matching (0-40 points)
        amount_diff = abs(transaction.amount - invoice.amount)
        if amount_diff <= self.amount_tolerance:
            score += 40
            details['amount_match'] = 'exact'
        elif amount_diff < 1.0:  # Within $1
            score += 30
            details['amount_match'] = 'close'
        else:
            details['amount_match'] = f'diff: ${amount_diff:.2f}'

        # 2. Invoice ID match in reference (50 points)
        extracted_id = self.extract_invoice_id_from_reference(transaction.reference)
        if extracted_id:
            details['extracted_id'] = extracted_id
            # Try to match with actual invoice IDs
            for inv in self.invoices:
                if extracted_id.upper() in inv.invoice_id.upper() or \
                   inv.invoice_id.upper() in extracted_id.upper():
                    if inv == invoice:
                        score += 50
                        details['invoice_id_match'] = 'exact'
                    break

        # 3. Merchant/Client name matching (0-20 points)
        merchant_code = self.extract_merchant_code(transaction.merchant)
        if merchant_code:
            name_score = self.fuzzy_match_score(merchant_code, invoice.client_name)
            score += name_score * 20
            details['name_score'] = f'{name_score:.2f}'

        # 4. Date proximity (0-10 points)
        # Payment should be after invoice date but within 30 days
        if invoice.date <= transaction.date <= invoice.date + timedelta(days=self.date_window_days):
            days_diff = (transaction.date - invoice.date).days
            # Give more points for payments closer to invoice date
            proximity_score = max(0, 10 - (days_diff / 3))
            score += proximity_score
            details['date_proximity'] = f'{days_diff} days after invoice'
        else:
            details['date_proximity'] = 'outside window'

        return score, details

    def match_transactions(self) -> List[MatchResult]:
        """
        Match all transactions to invoices.

        Strategy:
        1. For each transaction, calculate scores against all invoices
        2. Classify as: exact (>95), probable (70-95), ambiguous (45-70), no_match (<45)
        3. Handle ambiguities by flagging for manual review
        """
        self.matches = []
        used_invoices = set()

        for transaction in self.transactions:
            # Filter out non-Portal42 transactions
            if 'Portal42' not in transaction.merchant:
                result = MatchResult(
                    transaction=transaction,
                    invoice=None,
                    match_score=0,
                    match_type='no_match',
                    notes='Non-Portal42 transaction (transfer/fee)'
                )
                self.matches.append(result)
                continue

            # Score all available invoices
            scored_invoices = []
            for invoice in self.invoices:
                if invoice.invoice_id not in used_invoices:
                    score, details = self.score_match(transaction, invoice)
                    scored_invoices.append((invoice, score, details))

            # Sort by score (descending)
            scored_invoices.sort(key=lambda x: x[1], reverse=True)

            if not scored_invoices:
                # No unmatched invoices
                result = MatchResult(
                    transaction=transaction,
                    invoice=None,
                    match_score=0,
                    match_type='no_match',
                    notes='No available invoices to match'
                )
            else:
                top_invoice, top_score, top_details = scored_invoices[0]

                # Classify match type
                if top_score >= 95:
                    match_type = 'exact'
                    used_invoices.add(top_invoice.invoice_id)
                elif top_score >= 70:
                    match_type = 'probable'
                    # Only use if significantly better than second option
                    if len(scored_invoices) > 1:
                        second_score = scored_invoices[1][1]
                        if top_score - second_score > 20:
                            used_invoices.add(top_invoice.invoice_id)
                        else:
                            match_type = 'ambiguous'
                            top_invoice = None
                    else:
                        used_invoices.add(top_invoice.invoice_id)
                elif top_score >= 45:
                    match_type = 'ambiguous'
                    top_invoice = None
                else:
                    match_type = 'no_match'
                    top_invoice = None

                # Build notes
                notes = f"Score: {top_score:.1f} | "
                notes += " | ".join([f"{k}: {v}" for k, v in top_details.items()])

                if match_type == 'ambiguous' and len(scored_invoices) > 1:
                    second_inv, second_score, _ = scored_invoices[1]
                    notes += f" | 2nd: {second_inv.invoice_id} ({second_score:.1f})"

                result = MatchResult(
                    transaction=transaction,
                    invoice=top_invoice,
                    match_score=top_score,
                    match_type=match_type,
                    notes=notes
                )

            self.matches.append(result)

        return self.matches

    def get_summary(self) -> Dict:
        """Generate summary statistics of matching results"""
        total = len(self.matches)
        exact = sum(1 for m in self.matches if m.match_type == 'exact')
        probable = sum(1 for m in self.matches if m.match_type == 'probable')
        ambiguous = sum(1 for m in self.matches if m.match_type == 'ambiguous')
        no_match = sum(1 for m in self.matches if m.match_type == 'no_match')

        matched_amount = sum(m.transaction.amount for m in self.matches
                            if m.match_type in ['exact', 'probable'])
        total_amount = sum(m.transaction.amount for m in self.matches)

        return {
            'total_transactions': total,
            'exact_matches': exact,
            'probable_matches': probable,
            'ambiguous_matches': ambiguous,
            'unmatched_transactions': no_match,
            'total_transaction_amount': total_amount,
            'matched_amount': matched_amount,
            'unmatched_amount': total_amount - matched_amount,
            'match_confidence': (exact + probable) / total * 100 if total > 0 else 0
        }


def main():
    """Example usage of the matching engine"""
    engine = DartFreshBooksMatchEngine(
        amount_tolerance=0.01,
        date_window_days=30,
        fuzzy_match_threshold=0.85
    )

    # Load data
    engine.load_bank_statement('sample_dart_bank_statement.csv')
    engine.load_invoices('sample_freshbooks_invoices.csv')

    # Run matching
    matches = engine.match_transactions()

    # Print results
    print("\n=== MATCHING RESULTS ===\n")
    for result in matches:
        status_symbol = {
            'exact': '✓✓',
            'probable': '✓',
            'ambiguous': '?',
            'no_match': '✗'
        }[result.match_type]

        invoice_info = f"{result.invoice.invoice_id}" if result.invoice else "NONE"
        print(f"{status_symbol} {result.transaction.transaction_id} | "
              f"{result.transaction.merchant:30} | "
              f"${result.transaction.amount:10.2f} -> {invoice_info:15} | "
              f"{result.notes}")

    # Print summary
    summary = engine.get_summary()
    print(f"\n=== SUMMARY ===")
    print(f"Total transactions: {summary['total_transactions']}")
    print(f"Exact matches: {summary['exact_matches']}")
    print(f"Probable matches: {summary['probable_matches']}")
    print(f"Ambiguous: {summary['ambiguous_matches']}")
    print(f"Unmatched: {summary['unmatched_transactions']}")
    print(f"Match confidence: {summary['match_confidence']:.1f}%")
    print(f"Total amount: ${summary['total_transaction_amount']:.2f}")
    print(f"Matched amount: ${summary['matched_amount']:.2f}")


if __name__ == '__main__':
    main()
