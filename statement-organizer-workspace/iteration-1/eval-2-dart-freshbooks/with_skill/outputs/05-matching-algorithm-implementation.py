#!/usr/bin/env python3
"""
FreshBooks Transaction Matching Algorithm - Reference Implementation
Demonstrates the matching logic for Dart Bank transactions against Portal42 invoices
"""

from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class FreshBooksTransactionMatcher:
    """
    Matches Dart Bank transactions to FreshBooks unpaid invoices.

    Matching Strategy:
    1. Exact amount match (required)
    2. Fuzzy merchant name matching (optional, for disambiguation)
    3. Confidence scoring (90%+ = auto-mark, 70-89% = ambiguous, <70% = unmatched)
    """

    # Confidence thresholds
    MATCHED_THRESHOLD = 0.90  # 90%+ = auto-mark as paid
    AMBIGUOUS_THRESHOLD = 0.70  # 70-89% = needs review
    # Below 70% = unmatched

    def __init__(self):
        self.matched_invoices = []
        self.ambiguous_matches = []
        self.unmatched_transactions = []

    def match_transaction(
        self,
        transaction: Dict,
        unpaid_invoices: List[Dict]
    ) -> Dict:
        """
        Match a single transaction against all unpaid invoices.

        Transaction structure:
        {
            'date': '2026-03-10',
            'amount': 500.00,
            'merchant': 'ABC WELLNESS COLLECTIVE',
            'description': 'Payment for portal services'
        }

        Invoice structure:
        {
            'id': 'INV-FB-005421',
            'total': 500.00,
            'client_name': 'ABC Wellness Collective',
            'date': '2026-02-28'
        }

        Returns:
        {
            'status': 'matched' | 'ambiguous' | 'unmatched',
            'transaction': {...},
            'possible_matches': [...],
            'confidence': 0.95,
            'reason': 'Exact amount match with name confirmation'
        }
        """

        # Step 1: Find all invoices with exact amount match
        amount_matches = self._find_exact_amount_matches(
            transaction['amount'],
            unpaid_invoices
        )

        if not amount_matches:
            # No invoices match the transaction amount
            return {
                'status': 'unmatched',
                'transaction': transaction,
                'possible_matches': [],
                'confidence': 0.0,
                'reason': f"No invoice found matching amount ${transaction['amount']:.2f}"
            }

        if len(amount_matches) == 1:
            # Single invoice matches the amount - check merchant name
            invoice = amount_matches[0]
            confidence = self._calculate_confidence(transaction, invoice)

            if confidence >= self.MATCHED_THRESHOLD:
                return {
                    'status': 'matched',
                    'transaction': transaction,
                    'possible_matches': [invoice],
                    'confidence': confidence,
                    'reason': f"Exact amount match + high name confidence ({confidence:.1%})",
                    'invoice_id': invoice['id']
                }
            elif confidence >= self.AMBIGUOUS_THRESHOLD:
                return {
                    'status': 'ambiguous',
                    'transaction': transaction,
                    'possible_matches': [invoice],
                    'confidence': confidence,
                    'reason': f"Amount matches but name confidence is moderate ({confidence:.1%}). Review merchant name."
                }
            else:
                return {
                    'status': 'unmatched',
                    'transaction': transaction,
                    'possible_matches': [invoice],
                    'confidence': confidence,
                    'reason': f"Amount matches but merchant name is significantly different ({confidence:.1%})"
                }

        # Multiple invoices match the amount - use merchant name for disambiguation
        scored_matches = [
            {
                'invoice': invoice,
                'confidence': self._calculate_confidence(transaction, invoice)
            }
            for invoice in amount_matches
        ]

        # Sort by confidence (highest first)
        scored_matches.sort(key=lambda x: x['confidence'], reverse=True)
        best_match = scored_matches[0]

        if best_match['confidence'] >= self.MATCHED_THRESHOLD:
            # Top match has high confidence
            return {
                'status': 'matched',
                'transaction': transaction,
                'possible_matches': [best_match['invoice']],
                'confidence': best_match['confidence'],
                'reason': f"Among {len(amount_matches)} same-amount invoices, merchant name confirms: {best_match['invoice']['client_name']}"
            }
        elif best_match['confidence'] >= self.AMBIGUOUS_THRESHOLD:
            # Best match is ambiguous, or multiple invoices are close
            return {
                'status': 'ambiguous',
                'transaction': transaction,
                'possible_matches': amount_matches,
                'confidence': best_match['confidence'],
                'reason': f"Multiple invoices match amount ${transaction['amount']:.2f}. Best match: {best_match['invoice']['client_name']} ({best_match['confidence']:.1%} confidence)"
            }
        else:
            # Even the best match is weak
            return {
                'status': 'unmatched',
                'transaction': transaction,
                'possible_matches': amount_matches,
                'confidence': best_match['confidence'],
                'reason': f"Multiple invoices match amount but none have sufficient merchant name confidence (best: {best_match['confidence']:.1%})"
            }

    def _find_exact_amount_matches(
        self,
        amount: float,
        invoices: List[Dict]
    ) -> List[Dict]:
        """
        Find all invoices with exact amount match (within $0.01 tolerance for rounding).
        """
        tolerance = 0.01
        matches = [
            invoice for invoice in invoices
            if abs(invoice['total'] - amount) <= tolerance
        ]
        return matches

    def _calculate_confidence(
        self,
        transaction: Dict,
        invoice: Dict
    ) -> float:
        """
        Calculate confidence that this transaction matches this invoice.

        Components:
        - Amount match: Always 100 if we got this far (already filtered)
        - Name similarity: String similarity ratio between merchant and client_name

        Score = (amount_score + name_score) / 2
        """

        # Amount component (already guaranteed to match if we're here)
        amount_score = 1.0

        # Merchant name component
        merchant_from_bank = self._normalize_name(transaction['merchant'])
        client_name_from_fb = self._normalize_name(invoice['client_name'])

        name_similarity = SequenceMatcher(
            None,
            merchant_from_bank,
            client_name_from_fb
        ).ratio()

        # Weighted average (equal weight for now)
        combined_confidence = (amount_score + name_similarity) / 2.0

        return combined_confidence

    def _normalize_name(self, name: str) -> str:
        """
        Normalize merchant/client names for comparison.
        - Convert to lowercase
        - Remove extra whitespace
        - Remove common suffixes (Inc, LLC, Co, etc.)
        """
        import re

        # Convert to lowercase
        normalized = name.lower().strip()

        # Remove common suffixes
        suffixes = [
            r'\s+(inc|incorporated|llc|limited liability company|co|company|corp|corporation)$',
            r'\s+(collective|co-op|coop)$'
        ]
        for suffix_pattern in suffixes:
            normalized = re.sub(suffix_pattern, '', normalized)

        # Collapse extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def match_all_transactions(
        self,
        transactions: List[Dict],
        unpaid_invoices: List[Dict]
    ) -> Dict:
        """
        Match all transactions in a statement against all invoices.
        Returns categorized results.
        """
        results = {
            'matched': [],
            'ambiguous': [],
            'unmatched': []
        }

        for transaction in transactions:
            match_result = self.match_transaction(transaction, unpaid_invoices)

            # Add result to appropriate category
            results[match_result['status']].append(match_result)

            # Log the result
            logger.info(
                f"Transaction {transaction['date']} ${transaction['amount']:.2f} - "
                f"{match_result['status'].upper()}: {match_result['reason']}"
            )

        return results


# ============================================================================
# EXAMPLE USAGE & TEST DATA
# ============================================================================

def test_matching_algorithm():
    """
    Demonstrates the matching algorithm with example data.
    """

    # Sample Dart Bank transactions from March 2026 statement
    transactions = [
        {
            'date': '2026-03-05',
            'amount': 500.00,
            'merchant': 'ABC WELLNESS COLLECTIVE',
            'description': 'Portal42 client payment'
        },
        {
            'date': '2026-03-06',
            'amount': 300.00,
            'merchant': 'MEDSHOP',
            'description': 'Client payment'
        },
        {
            'date': '2026-03-10',
            'amount': 1000.00,
            'merchant': 'ABC WELLNESS COLLECTIVE',
            'description': 'Payment'
        },
        {
            'date': '2026-03-15',
            'amount': 625.00,
            'merchant': 'NATURAL REMEDY CO',
            'description': 'Client payment'
        },
        {
            'date': '2026-03-20',
            'amount': 100.00,
            'merchant': 'UNKNOWN VENDOR LLC',
            'description': 'Unknown payment'
        }
    ]

    # Sample unpaid FreshBooks invoices for Portal42
    unpaid_invoices = [
        {
            'id': 'INV-FB-005421',
            'total': 500.00,
            'client_name': 'ABC Wellness Collective',
            'date': '2026-02-28'
        },
        {
            'id': 'INV-FB-005422',
            'total': 750.00,
            'client_name': 'Green Leaf Farms',
            'date': '2026-02-25'
        },
        {
            'id': 'INV-FB-005423',
            'total': 300.00,
            'client_name': 'MedShop Inc',
            'date': '2026-03-01'
        },
        {
            'id': 'INV-FB-005424',
            'total': 300.00,
            'client_name': 'MedShop Chicago',
            'date': '2026-03-02'
        },
        {
            'id': 'INV-FB-005425',
            'total': 625.00,
            'client_name': 'Natural Remedy',
            'date': '2026-03-03'
        }
    ]

    # Run matching algorithm
    matcher = FreshBooksTransactionMatcher()
    results = matcher.match_all_transactions(transactions, unpaid_invoices)

    # Print results
    print("\n" + "="*70)
    print("FRESHBOOKS MATCHING ALGORITHM - TEST RESULTS")
    print("="*70 + "\n")

    print(f"MATCHED INVOICES ({len(results['matched'])}):")
    for match in results['matched']:
        print(f"  ✓ {match['transaction']['date']} ${match['transaction']['amount']:.2f} "
              f"-> {match['possible_matches'][0]['id']} "
              f"({match['confidence']:.1%})")
        print(f"    Reason: {match['reason']}\n")

    print(f"\nAMBIGUOUS MATCHES ({len(results['ambiguous'])}):")
    for match in results['ambiguous']:
        possible = [f"{m['id']}" for m in match['possible_matches']]
        print(f"  ⚠ {match['transaction']['date']} ${match['transaction']['amount']:.2f} "
              f"-> {', '.join(possible)} "
              f"({match['confidence']:.1%})")
        print(f"    Reason: {match['reason']}\n")

    print(f"\nUNMATCHED TRANSACTIONS ({len(results['unmatched'])}):")
    for match in results['unmatched']:
        print(f"  ✗ {match['transaction']['date']} ${match['transaction']['amount']:.2f}")
        print(f"    Reason: {match['reason']}\n")

    # Summary statistics
    total_amount = sum(t['amount'] for t in transactions)
    matched_amount = sum(m['transaction']['amount'] for m in results['matched'])
    ambiguous_amount = sum(m['transaction']['amount'] for m in results['ambiguous'])
    unmatched_amount = sum(m['transaction']['amount'] for m in results['unmatched'])

    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)
    print(f"Total transactions: {len(transactions)}")
    print(f"Total amount: ${total_amount:.2f}")
    print(f"\nMatched:     {len(results['matched']):2d} transactions | ${matched_amount:10.2f} ({matched_amount/total_amount:.1%})")
    print(f"Ambiguous:   {len(results['ambiguous']):2d} transactions | ${ambiguous_amount:10.2f} ({ambiguous_amount/total_amount:.1%})")
    print(f"Unmatched:   {len(results['unmatched']):2d} transactions | ${unmatched_amount:10.2f} ({unmatched_amount/total_amount:.1%})")
    print("\n" + "="*70)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    test_matching_algorithm()
