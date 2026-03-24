#!/usr/bin/env python3
"""
Statement Organizer CLI
Easy command-line interface for processing statements
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import argparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.process_statement import StatementProcessor


def main():
    parser = argparse.ArgumentParser(
        description='Statement Organizer - Automated statement processing and FreshBooks integration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py process /Statements/Personal/Joint/Banks/Banco-Popular-2026-03.csv
  python cli.py learn /Statements/Personal/You/Banks/NewBank-2026-03.csv
  python cli.py process-all /Statements/
  python cli.py freshbooks /Statements/Business-You/Banks/Dart-Bank-2026-03.csv
  python cli.py report /Statements/Logs/
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Process single statement
    process_parser = subparsers.add_parser('process', help='Process a single statement file')
    process_parser.add_argument('file', help='Path to statement CSV file')
    process_parser.add_argument('--account', help='Account type (personal/business/joint)')
    process_parser.add_argument('--bank', help='Manually specify bank name')

    # Learn format from new statement
    learn_parser = subparsers.add_parser('learn', help='Learn format from a new statement')
    learn_parser.add_argument('file', help='Path to statement CSV file')
    learn_parser.add_argument('--bank', required=True, help='Bank/card name')

    # Process all statements
    all_parser = subparsers.add_parser('process-all', help='Process all statements in a directory')
    all_parser.add_argument('directory', help='Directory containing statements')
    all_parser.add_argument('--recursive', action='store_true', help='Process recursively')

    # FreshBooks sync
    freshbooks_parser = subparsers.add_parser('freshbooks', help='Sync Dart Bank statement with FreshBooks')
    freshbooks_parser.add_argument('file', help='Path to Dart Bank statement CSV')
    freshbooks_parser.add_argument('--dry-run', action='store_true', help='Show what would be marked without marking')

    # View reports
    report_parser = subparsers.add_parser('report', help='View processing reports')
    report_parser.add_argument('--logs', help='View logs from directory')
    report_parser.add_argument('--latest', action='store_true', help='Show latest log')

    # Check status
    status_parser = subparsers.add_parser('status', help='Check statement processing status')
    status_parser.add_argument('--directory', default='Statements', help='Statements directory')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    processor = StatementProcessor()

    # Route commands
    if args.command == 'process':
        print(f"📄 Processing statement: {args.file}")
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File not found: {args.file}")
            return 1

        bank = args.bank or processor.detect_bank(args.file)
        if not bank:
            print("⚠️  Could not detect bank. Use --bank to specify.")
            return 1

        transactions = processor.parse_statement(args.file, bank)
        print(f"✓ Parsed {len(transactions)} transactions")
        print(f"✓ Bank detected: {bank}")
        print(f"✓ Format saved to .statement-formats.json")
        return 0

    elif args.command == 'learn':
        print(f"🧠 Learning format for {args.bank}: {args.file}")
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File not found: {args.file}")
            return 1

        mapping = processor.learn_format(args.file, args.bank)
        if mapping:
            print(f"✓ Format learned and saved for {args.bank}")
            print(f"✓ Detected columns: {', '.join(mapping.get('detected_fields', [])[:5])}")
            return 0
        else:
            print(f"❌ Could not learn format")
            return 1

    elif args.command == 'process-all':
        print(f"🚀 Processing all statements in {args.directory}")
        directory = Path(args.directory)
        if not directory.exists():
            print(f"❌ Directory not found: {args.directory}")
            return 1

        # Find all CSV files
        pattern = '**/*.csv' if args.recursive else '*.csv'
        csv_files = list(directory.glob(pattern))
        print(f"Found {len(csv_files)} CSV files")

        processed = 0
        for csv_file in csv_files:
            print(f"  Processing: {csv_file.name}...", end=' ')
            bank = processor.detect_bank(str(csv_file))
            if bank:
                transactions = processor.parse_statement(str(csv_file), bank)
                print(f"✓ {len(transactions)} transactions")
                processed += 1
            else:
                print("⚠️  Skipped (bank not detected)")

        print(f"\n✓ Processed {processed} statements")
        return 0

    elif args.command == 'freshbooks':
        print(f"💰 Syncing with FreshBooks: {args.file}")
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File not found: {args.file}")
            return 1

        transactions = processor.parse_statement(args.file, 'Dart Bank')
        matches = processor.match_with_freshbooks(transactions, datetime.now().strftime('%Y-%m-%d'))

        print(f"✓ Matched: {len(matches['matched'])} invoices")
        print(f"⚠️  Ambiguous: {len(matches['ambiguous'])} (needs review)")
        print(f"○ Unmatched: {len(matches['unmatched'])} transactions")

        if not args.dry_run:
            report = processor.generate_report(matches, datetime.now().strftime('%Y-%m-%d'))
            print(f"\n✓ Report saved: {report}")
        else:
            print("\n[DRY RUN] No changes made to FreshBooks")

        return 0

    elif args.command == 'report':
        if args.latest:
            log_dir = Path('Statements/Logs')
            if log_dir.exists():
                logs = sorted(log_dir.glob('*.log'))
                if logs:
                    print(f"Latest log: {logs[-1]}")
                    with open(logs[-1], 'r') as f:
                        print(f.read())
                    return 0
            print("No logs found")
            return 1

        if args.logs:
            log_dir = Path(args.logs)
            if log_dir.exists():
                print(f"📋 Reports in {args.logs}:\n")
                for file in sorted(log_dir.glob('*')):
                    size = file.stat().st_size
                    print(f"  {file.name} ({size} bytes)")
                return 0
            print(f"❌ Directory not found: {args.logs}")
            return 1

    elif args.command == 'status':
        directory = Path(args.directory)
        if not directory.exists():
            print(f"❌ Directory not found: {args.directory}")
            return 1

        print(f"📊 Statement Processing Status\n")

        # Count files by folder
        for folder in directory.rglob('*'):
            if folder.is_dir() and folder.name not in ['Logs', '__pycache__']:
                csv_files = list(folder.glob('*.csv'))
                if csv_files:
                    print(f"{folder.relative_to(directory)}: {len(csv_files)} files")

        # Check for format mappings
        formats_file = directory / '.statement-formats.json'
        if formats_file.exists():
            import json
            with open(formats_file) as f:
                formats = json.load(f)
            print(f"\n✓ {len(formats)} formats learned")

        # Check logs
        logs_dir = directory / 'Logs'
        if logs_dir.exists():
            logs = list(logs_dir.glob('*.log'))
            print(f"✓ {len(logs)} log files")

        return 0


if __name__ == '__main__':
    sys.exit(main())
