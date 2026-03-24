"""
Generate matching reports from Dart Bank statement and FreshBooks invoices.
This script runs the matching algorithm and produces multiple output formats.
"""

import csv
import sys
from datetime import datetime
from matching_algorithm import DartFreshBooksMatchEngine


def generate_csv_report(engine: DartFreshBooksMatchEngine, output_file: str):
    """
    Generate a CSV report of all matching results.

    Columns:
    - TransactionID
    - Date
    - Merchant
    - Amount
    - Reference
    - MatchedInvoiceID
    - ClientName
    - MatchScore
    - MatchType
    - Details/Notes
    """
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'TransactionID',
            'Date',
            'Merchant',
            'Amount',
            'Reference',
            'MatchedInvoiceID',
            'ClientName',
            'InvoiceAmount',
            'MatchScore',
            'MatchType',
            'Details'
        ])
        writer.writeheader()

        for match in engine.matches:
            writer.writerow({
                'TransactionID': match.transaction.transaction_id,
                'Date': match.transaction.date.strftime('%Y-%m-%d'),
                'Merchant': match.transaction.merchant,
                'Amount': f"{match.transaction.amount:.2f}",
                'Reference': match.transaction.reference,
                'MatchedInvoiceID': match.invoice.invoice_id if match.invoice else 'UNMATCHED',
                'ClientName': match.invoice.client_name if match.invoice else 'N/A',
                'InvoiceAmount': f"{match.invoice.amount:.2f}" if match.invoice else 'N/A',
                'MatchScore': f"{match.match_score:.1f}",
                'MatchType': match.match_type.upper(),
                'Details': match.notes
            })


def generate_reconciliation_report(engine: DartFreshBooksMatchEngine,
                                   output_file: str):
    """
    Generate a detailed reconciliation report showing:
    - Transactions marked as paid (matched)
    - Transactions requiring review (ambiguous/no_match)
    - Summary statistics
    """
    with open(output_file, 'w') as f:
        f.write("=" * 100 + "\n")
        f.write("DART BANK STATEMENT TO FRESHBOOKS INVOICE RECONCILIATION REPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 100 + "\n\n")

        # Summary section
        summary = engine.get_summary()
        f.write("RECONCILIATION SUMMARY\n")
        f.write("-" * 100 + "\n")
        f.write(f"Total Transactions Processed:     {summary['total_transactions']}\n")
        f.write(f"Exact Matches (High Confidence):  {summary['exact_matches']}\n")
        f.write(f"Probable Matches (Medium):        {summary['probable_matches']}\n")
        f.write(f"Ambiguous (Needs Review):         {summary['ambiguous_matches']}\n")
        f.write(f"Unmatched Transactions:           {summary['unmatched_transactions']}\n")
        f.write(f"Overall Match Confidence:         {summary['match_confidence']:.1f}%\n")
        f.write(f"\nTotal Transaction Amount:         ${summary['total_transaction_amount']:>12.2f}\n")
        f.write(f"Matched to Invoices:              ${summary['matched_amount']:>12.2f}\n")
        f.write(f"Unmatched Amount:                 ${summary['unmatched_amount']:>12.2f}\n")
        f.write("\n\n")

        # Marked as Paid section
        f.write("TRANSACTIONS MARKED AS PAID\n")
        f.write("(Exact and Probable matches - safe to mark as paid in FreshBooks)\n")
        f.write("-" * 100 + "\n")
        f.write(f"{'TxnID':<20} {'Date':<12} {'Merchant':<30} {'Amount':>12} {'Invoice':<15} {'Score':>8}\n")
        f.write("-" * 100 + "\n")

        paid_total = 0
        for match in engine.matches:
            if match.match_type in ['exact', 'probable']:
                paid_total += match.transaction.amount
                f.write(f"{match.transaction.transaction_id:<20} "
                       f"{match.transaction.date.strftime('%Y-%m-%d'):<12} "
                       f"{match.transaction.merchant[:30]:<30} "
                       f"${match.transaction.amount:>11.2f} "
                       f"{match.invoice.invoice_id:<15} "
                       f"{match.match_score:>7.1f}\n")

        f.write("-" * 100 + "\n")
        f.write(f"TOTAL MARKED PAID: ${paid_total:>85.2f}\n\n\n")

        # Requiring Review section
        f.write("TRANSACTIONS REQUIRING MANUAL REVIEW\n")
        f.write("(Ambiguous matches or unmatched - verify before marking as paid)\n")
        f.write("-" * 100 + "\n")
        f.write(f"{'TxnID':<20} {'Date':<12} {'Merchant':<30} {'Amount':>12} {'Status':<15} {'Details':<50}\n")
        f.write("-" * 100 + "\n")

        review_total = 0
        for match in engine.matches:
            if match.match_type in ['ambiguous', 'no_match']:
                review_total += match.transaction.amount
                status = "AMBIGUOUS" if match.match_type == 'ambiguous' else "NOT FOUND"
                f.write(f"{match.transaction.transaction_id:<20} "
                       f"{match.transaction.date.strftime('%Y-%m-%d'):<12} "
                       f"{match.transaction.merchant[:30]:<30} "
                       f"${match.transaction.amount:>11.2f} "
                       f"{status:<15} ")
                # Truncate notes if too long
                notes = match.notes[:45] + "..." if len(match.notes) > 45 else match.notes
                f.write(f"{notes:<50}\n")

        f.write("-" * 100 + "\n")
        f.write(f"TOTAL REQUIRING REVIEW: ${review_total:>81.2f}\n\n\n")

        # Detailed Review section
        f.write("DETAILED REVIEW INFORMATION\n")
        f.write("-" * 100 + "\n")
        for match in engine.matches:
            if match.match_type in ['ambiguous', 'no_match']:
                f.write(f"\nTransaction: {match.transaction.transaction_id}\n")
                f.write(f"  Date:      {match.transaction.date.strftime('%Y-%m-%d')}\n")
                f.write(f"  Merchant:  {match.transaction.merchant}\n")
                f.write(f"  Amount:    ${match.transaction.amount:.2f}\n")
                f.write(f"  Reference: {match.transaction.reference}\n")
                f.write(f"  Status:    {match.match_type.upper()}\n")
                f.write(f"  Notes:     {match.notes}\n")


def generate_unmatched_invoices_report(engine: DartFreshBooksMatchEngine,
                                       output_file: str):
    """
    Generate a report of invoices that were not matched to any transaction.
    These invoices may still be outstanding or need follow-up.
    """
    matched_invoice_ids = {match.invoice.invoice_id
                          for match in engine.matches
                          if match.invoice is not None}

    unmatched_invoices = [inv for inv in engine.invoices
                         if inv.invoice_id not in matched_invoice_ids]

    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("UNMATCHED INVOICES REPORT\n")
        f.write("(Invoices with no corresponding bank transaction)\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Total Unmatched Invoices: {len(unmatched_invoices)}\n")
        unmatched_total = sum(inv.amount for inv in unmatched_invoices)
        f.write(f"Total Unmatched Amount: ${unmatched_total:.2f}\n\n")

        f.write(f"{'InvoiceID':<15} {'Client':<25} {'Amount':>12} {'Date':<12} {'Status':<10}\n")
        f.write("-" * 80 + "\n")

        for invoice in sorted(unmatched_invoices, key=lambda x: x.date):
            f.write(f"{invoice.invoice_id:<15} "
                   f"{invoice.client_name[:25]:<25} "
                   f"${invoice.amount:>11.2f} "
                   f"{invoice.date.strftime('%Y-%m-%d'):<12} "
                   f"{invoice.status:<10}\n")


def main():
    """Main entry point - process statement and generate all reports"""
    # Initialize matching engine
    engine = DartFreshBooksMatchEngine(
        amount_tolerance=0.01,
        date_window_days=30,
        fuzzy_match_threshold=0.85
    )

    # Load data
    print("Loading bank statement...")
    engine.load_bank_statement('sample_dart_bank_statement.csv')
    print(f"  Loaded {len(engine.transactions)} transactions")

    print("Loading FreshBooks invoices...")
    engine.load_invoices('sample_freshbooks_invoices.csv')
    print(f"  Loaded {len(engine.invoices)} invoices")

    # Run matching
    print("\nMatching transactions to invoices...")
    matches = engine.match_transactions()

    # Generate reports
    print("\nGenerating reports...")

    # Report 1: Detailed CSV with all matches
    csv_report = 'outputs/dart_freshbooks_matching_report.csv'
    generate_csv_report(engine, csv_report)
    print(f"  ✓ CSV Report: {csv_report}")

    # Report 2: Reconciliation summary with paid/review sections
    reconciliation_report = 'outputs/reconciliation_summary.txt'
    generate_reconciliation_report(engine, reconciliation_report)
    print(f"  ✓ Reconciliation Report: {reconciliation_report}")

    # Report 3: Unmatched invoices
    unmatched_report = 'outputs/unmatched_invoices.txt'
    generate_unmatched_invoices_report(engine, unmatched_report)
    print(f"  ✓ Unmatched Invoices Report: {unmatched_report}")

    print("\nReports generated successfully!")


if __name__ == '__main__':
    main()
