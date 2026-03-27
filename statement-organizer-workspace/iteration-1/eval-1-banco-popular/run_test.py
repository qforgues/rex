#!/usr/bin/env python3
"""
Test harness for statement-organizer skill
Processes a Banco Popular statement and generates outputs
"""

import sys
import os
import json
import csv
from pathlib import Path
from datetime import datetime

# Add the skill scripts to path
skill_scripts = Path("/sessions/amazing-sharp-clarke/mnt/rex/statement-organizer/scripts")
sys.path.insert(0, str(skill_scripts))

from process_statement import StatementProcessor

# Setup directories
test_root = Path("/sessions/amazing-sharp-clarke/mnt/rex/statement-organizer-workspace/iteration-1/eval-1-banco-popular")
test_statements = test_root / "test_statements"
outputs = test_root / "with_skill/outputs"

# Create output directories
outputs.mkdir(parents=True, exist_ok=True)

# Change to test directory to simulate running from there
os.chdir(test_statements)

print("=" * 80)
print("STATEMENT ORGANIZER TEST - BANCO POPULAR JOINT ACCOUNT")
print("=" * 80)
print(f"\nTest directory: {test_statements}")
print(f"Statement file: Banco-Popular-Joint-2026-03.csv")
print(f"Output directory: {outputs}")
print()

# Initialize processor
processor = StatementProcessor(statements_dir=str(test_statements))

statement_file = test_statements / "Personal/Joint/Banks/Banco-Popular-Joint-2026-03.csv"

print("STEP 1: BANK DETECTION")
print("-" * 80)
detected_bank = processor.detect_bank(str(statement_file))
print(f"Detected bank: {detected_bank}")
print()

print("STEP 2: FORMAT LEARNING")
print("-" * 80)
format_info = processor.learn_format(str(statement_file), detected_bank)
print(f"Format mapping created:")
print(json.dumps(format_info, indent=2))
print()

print("STEP 3: TRANSACTION PARSING")
print("-" * 80)
transactions = processor.parse_statement(str(statement_file), detected_bank)
print(f"Total transactions parsed: {len(transactions)}")
print("\nSample transactions (first 5):")
for i, tx in enumerate(transactions[:5], 1):
    print(f"  {i}. {tx['date']} | {tx['merchant']:30} | Amount: {tx['amount']:10.2f}")
print()

print("STEP 4: FRESHBOOKS MATCHING (N/A for Banco Popular)")
print("-" * 80)
matches = processor.match_with_freshbooks(transactions, "2026-03")
print(f"Matched: {len(matches['matched'])} | Ambiguous: {len(matches['ambiguous'])} | Unmatched: {len(matches['unmatched'])}")
print("(FreshBooks sync only applies to Dart Bank accounts)")
print()

print("STEP 5: REPORT GENERATION")
print("-" * 80)
report_path = processor.generate_report(matches, "2026-03")
print(f"Report generated: {report_path}")
print()

# Now copy all outputs to the designated outputs folder
print("STEP 6: COLLECTING OUTPUTS")
print("-" * 80)

# Copy the format mapping
formats_file = test_statements / ".statement-formats.json"
if formats_file.exists():
    import shutil
    output_formats = outputs / ".statement-formats.json"
    shutil.copy(formats_file, output_formats)
    print(f"✓ Format mapping: {output_formats}")

# Copy the logs
logs_dir = test_statements / "Logs"
if logs_dir.exists():
    import shutil
    output_logs = outputs / "Logs"
    if output_logs.exists():
        shutil.rmtree(output_logs)
    shutil.copytree(logs_dir, output_logs)
    print(f"✓ Logs directory: {output_logs}")

    # List log files
    for log_file in output_logs.glob("*.log"):
        print(f"  - {log_file.name}")
    for csv_file in output_logs.glob("*.csv"):
        print(f"  - {csv_file.name}")

# Create a parsed transactions log
transactions_log = outputs / "parsed-transactions.csv"
with open(transactions_log, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Date', 'Merchant', 'Amount', 'Type'])
    for tx in transactions:
        tx_type = 'Debit' if tx['amount'] < 0 else 'Credit'
        writer.writerow([tx['date'], tx['merchant'], f"{tx['amount']:.2f}", tx_type])
print(f"✓ Parsed transactions: {transactions_log}")
print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print(f"\nAll outputs saved to: {outputs}")
