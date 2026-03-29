"""
GL CSV Profile Parsers for FreshBooks and QuickBooks Online.

Parsers for General Ledger CSV exports from FreshBooks and QBO, converting them
to the Rex transaction format for tax categorization and analysis.
"""

import csv
import re
from datetime import datetime
from typing import Optional
from q42_db import Q42_TAX_CATEGORIES


# ---------------------------------------------------------------------------
# Category Mapping: FreshBooks Transaction Type & Account → Tax Category
# ---------------------------------------------------------------------------

FRESHBOOKS_CATEGORY_MAP = {
    # Mappings based on transaction type and account type
    "expense": {
        "Bank Fees & Interest": "Bank Fees & Interest",
        "Insurance": "Insurance (Business)",
        "Meals": "Business Meals (50%)",
        "Travel": "Business Travel",
        "Supplies": "Office Supplies",
        "Equipment": "Equipment (Section 179)",
        "Software": "Technology & Software",
        "Utilities": "Utilities (Business %)",
        "Rent": "Rent & Lease (Business)",
        "Payroll": "Payroll & Contractors",
        "Professional": "Professional Services",
        "Legal": "Legal & Accounting",
        "Marketing": "Marketing & Advertising",
        "Training": "Education & Training",
    },
    "payment": {
        # Payments are typically income or transfers
        "default": "Income",
    },
    "initial_balance": {
        # Skip these entirely
        "default": None,
    },
}


QBO_CATEGORY_MAP = {
    # Maps account names and transaction types to tax categories
    "Expense": {
        "meals": "Business Meals (50%)",
        "travel": "Business Travel",
        "entertainment": "Business Travel",
        "office supplies": "Office Supplies",
        "equipment": "Equipment (Section 179)",
        "software": "Technology & Software",
        "subscriptions": "Subscriptions (Business)",
        "utilities": "Utilities (Business %)",
        "rent": "Rent & Lease (Business)",
        "lease": "Rent & Lease (Business)",
        "insurance": "Insurance (Business)",
        "professional": "Professional Services",
        "legal": "Legal & Accounting",
        "accounting": "Legal & Accounting",
        "marketing": "Marketing & Advertising",
        "advertising": "Marketing & Advertising",
        "training": "Education & Training",
        "education": "Education & Training",
        "bank fee": "Bank Fees & Interest",
        "fee": "Bank Fees & Interest",
        "interest": "Bank Fees & Interest",
        "payroll": "Payroll & Contractors",
        "contractor": "Payroll & Contractors",
        "business expenses": "Uncategorized",  # Too vague
        "personal": "Personal (Non-Deductible)",
        "transfer": "Transfer",
        "deposit": "Income",
        "default": "Uncategorized",
    },
    "Payment": {
        # Payment = outflow, often income-related or loan payment
        "default": "Income",
    },
    "Deposit": {
        # Deposit = inflow = income
        "default": "Income",
    },
    "Opening": {
        # Skip opening balances
        "default": None,
    },
}


def _map_freshbooks_category(transaction_type: str, account_type: str, note: str) -> Optional[str]:
    """
    Map a FreshBooks transaction to a tax category.

    Parameters
    ----------
    transaction_type : str
        Transaction type (e.g., "expense", "payment", "initial_balance")
    account_type : str
        Account Sub Type (e.g., "Cash & Bank", "Bank Fees & Interest")
    note : str
        Transaction note/description

    Returns
    -------
    Optional[str]
        Tax category name, or None to skip this transaction
    """
    # Skip initial balance entries
    if transaction_type.lower() == "initial_balance":
        return None

    ttype = transaction_type.lower()
    note_lower = (note or "").lower()
    account_lower = (account_type or "").lower()

    # Special patterns in notes for FreshBooks
    if "payroll" in note_lower or "pay " in note_lower or "ppd trace" in note_lower:
        return "Payroll & Contractors"
    if "fee" in note_lower or "tran fee" in note_lower:
        return "Bank Fees & Interest"
    if "credit" in note_lower and "card" in note_lower:
        return "Bank Fees & Interest"
    if "transfer" in note_lower:
        return "Transfer"

    # By transaction type
    if ttype == "expense":
        # Most expenses from bank accounts are fees or payments
        if "fee" in note_lower or "interest" in note_lower:
            return "Bank Fees & Interest"
        return "Uncategorized"

    if ttype == "payment":
        # Positive payments from a bank account typically indicate transfers in or income
        return "Business Income"

    return "Uncategorized"


def _map_qbo_category(account_name: str, transaction_type: str, memo: str) -> Optional[str]:
    """
    Map a QBO transaction to a tax category.

    Parameters
    ----------
    account_name : str
        Account name from QBO
    transaction_type : str
        Transaction type (e.g., "Expense", "Deposit", "Payment")
    memo : str
        Transaction memo/description

    Returns
    -------
    Optional[str]
        Tax category name, or None to skip this transaction
    """
    account_lower = (account_name or "").lower()
    memo_lower = (memo or "").lower()
    ttype = transaction_type.lower() if transaction_type else ""

    # Skip opening balances
    if "opening" in account_lower or "opening" in memo_lower or "beginning" in memo_lower:
        return None

    # Special patterns to map first
    if "quickbooks" in memo_lower and "fee" in memo_lower:
        return "Bank Fees & Interest"
    if "payroll" in memo_lower or "payroll" in account_lower:
        return "Payroll & Contractors"
    if "personal" in account_lower:
        return "Personal (Non-Deductible)"

    # By transaction type
    if ttype == "deposit":
        return "Business Income"
    elif ttype == "payment":
        # Without more context, we can't categorize payments further
        # They could be vendor payments, loan payments, etc.
        # Map by account name if available
        if "personal" in account_lower:
            return "Personal (Non-Deductible)"
        return "Uncategorized"
    elif ttype == "expense":
        # Try to categorize by account name
        if "meals" in account_lower or "dining" in account_lower:
            return "Business Meals (50%)"
        elif "travel" in account_lower:
            return "Business Travel"
        elif "office" in account_lower or "supplies" in account_lower:
            return "Office Supplies"
        elif "equipment" in account_lower:
            return "Equipment (Section 179)"
        elif "software" in account_lower or "technology" in account_lower:
            return "Technology & Software"
        elif "utilities" in account_lower:
            return "Utilities (Business %)"
        elif "rent" in account_lower or "lease" in account_lower:
            return "Rent & Lease (Business)"
        elif "insurance" in account_lower:
            return "Insurance (Business)"
        elif "professional" in account_lower or "legal" in account_lower:
            return "Professional Services"
        elif "marketing" in account_lower or "advertising" in account_lower:
            return "Marketing & Advertising"
        elif "training" in account_lower or "education" in account_lower:
            return "Education & Training"
        elif "bank" in account_lower or "fee" in account_lower or "interest" in account_lower:
            return "Bank Fees & Interest"
        elif "personal" in account_lower:
            return "Personal (Non-Deductible)"
        return "Uncategorized"

    return "Uncategorized"


# ---------------------------------------------------------------------------
# FreshBooks GL CSV Parser
# ---------------------------------------------------------------------------

def parse_freshbooks_gl(filepath: str) -> list[dict]:
    """
    Parse a FreshBooks General Ledger CSV export into Rex transaction format.

    Format:
        Headers: Account Number, Account Type, Account Sub Type, Parent Account: Sub Account,
                 Related Account, Date, Transaction Type, Transaction Identifier, Client,
                 Vendor, Project, Note, Amount, Debit, Credit, Running Balance, Currency, Matched

    Returns
    -------
    list[dict]
        List of transaction dicts with keys:
        - date (YYYY-MM-DD)
        - description (string)
        - merchant_name (string or empty)
        - amount (float, negative for expenses, positive for income)
        - tax_category (string)
        - data_source ("freshbooks")
    """
    transactions = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows
                if not row or not any(row.values()):
                    continue

                # Parse date
                date_str = row.get("Date", "").strip()
                if not date_str:
                    continue
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_iso = date_obj.strftime("%Y-%m-%d")
                except Exception:
                    continue

                # Get transaction type and skip initial_balance
                ttype = row.get("Transaction Type", "").strip().lower()
                if ttype == "initial_balance":
                    continue

                # Get account and note info
                account_sub_type = row.get("Account Sub Type", "").strip()
                note = row.get("Note", "").strip()

                # Map to tax category
                tax_cat = _map_freshbooks_category(ttype, account_sub_type, note)
                if tax_cat is None:
                    # Skip this transaction type (e.g., initial_balance)
                    continue

                # Get amount - use Amount column which is signed (negative for expenses)
                amount_str = row.get("Amount", "0").strip()
                try:
                    amount = float(amount_str.replace(",", ""))
                except ValueError:
                    continue

                # Get merchant/vendor info
                client = row.get("Client", "").strip()
                vendor = row.get("Vendor", "").strip()
                merchant_name = vendor or client or ""

                # Build description
                description = note if note else ttype.title()

                transactions.append({
                    "date": date_iso,
                    "description": description,
                    "merchant_name": merchant_name,
                    "amount": amount,
                    "tax_category": tax_cat,
                    "data_source": "freshbooks",
                })

    except Exception as e:
        raise ValueError(f"Error parsing FreshBooks GL CSV: {e}")

    return transactions


# ---------------------------------------------------------------------------
# QBO GL CSV Parser
# ---------------------------------------------------------------------------

def parse_qbo_gl(filepath: str) -> list[dict]:
    """
    Parse a QuickBooks Online General Ledger CSV export into Rex transaction format.

    QBO Format:
        Row 1: Company name
        Row 2: Report name
        Row 3: Date range
        Row 4: blank
        Row 5: Headers (empty first column, then Date, Transaction Type, Num, Name,
                        Memo/Description, Account, Debit, Credit, Balance)
        Row 6+: Data rows and section headers/totals

    Returns
    -------
    list[dict]
        List of transaction dicts with keys:
        - date (YYYY-MM-DD)
        - description (string)
        - merchant_name (string)
        - amount (float, negative for expenses, positive for income)
        - tax_category (string)
        - data_source ("qbo")
    """
    transactions = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

            # Skip first 4 rows (company, report name, date range, blank)
            data_start = 5  # Row 5 is headers (0-indexed = row 4)

            if len(rows) <= data_start:
                return []

            # Parse data rows starting from row 6 (index 5)
            current_section = None

            for row_idx in range(data_start, len(rows)):
                row = rows[row_idx]

                # QBO structure: first column is empty for data rows,
                # but contains section headers or "Total for..." for meta rows
                first_col = row[0].strip() if row and len(row) > 0 else ""

                # Skip section headers and total rows
                if first_col and (first_col.startswith("Total for") or
                                  (len(row) <= 2 or not row[1].strip())):
                    if first_col and not first_col.startswith("Total for"):
                        current_section = first_col
                    continue

                # Data row should have at least: blank, date, type, num, name, memo, account, debit, credit
                if len(row) < 8:
                    continue

                # Extract columns (accounting for first empty column)
                date_str = row[1].strip() if len(row) > 1 else ""
                ttype = row[2].strip() if len(row) > 2 else ""
                # num = row[3].strip() if len(row) > 3 else ""
                name = row[4].strip() if len(row) > 4 else ""
                memo = row[5].strip() if len(row) > 5 else ""
                account = row[6].strip() if len(row) > 6 else ""
                debit_str = row[7].strip() if len(row) > 7 else ""
                credit_str = row[8].strip() if len(row) > 8 else ""

                # Skip if no date
                if not date_str or date_str.lower() in ("date", "opening"):
                    continue

                # Skip opening balance entries
                if "opening" in ttype.lower() or "beginning" in account.lower():
                    continue

                # Parse date (MM/DD/YYYY format)
                try:
                    date_obj = datetime.strptime(date_str, "%m/%d/%Y")
                    date_iso = date_obj.strftime("%Y-%m-%d")
                except Exception:
                    continue

                # Parse debit/credit (handle comma-separated thousands and spaces)
                debit_val = 0.0
                credit_val = 0.0

                try:
                    if debit_str:
                        debit_cleaned = debit_str.replace(",", "").replace("$", "").strip()
                        debit_val = float(debit_cleaned) if debit_cleaned else 0.0
                except ValueError:
                    pass

                try:
                    if credit_str:
                        credit_cleaned = credit_str.replace(",", "").replace("$", "").strip()
                        credit_val = float(credit_cleaned) if credit_cleaned else 0.0
                except ValueError:
                    pass

                # Calculate amount: debit = positive (asset increase), credit = negative (asset decrease)
                # From business perspective: payment received (credit to bank) = positive income
                # Payment made (debit to bank) = negative expense
                amount = debit_val - credit_val

                # Map to tax category
                tax_cat = _map_qbo_category(account, ttype, memo)
                if tax_cat is None:
                    continue

                # Build description
                description = memo if memo else ttype

                transactions.append({
                    "date": date_iso,
                    "description": description,
                    "merchant_name": name,
                    "amount": amount,
                    "tax_category": tax_cat,
                    "data_source": "qbo",
                })

    except Exception as e:
        raise ValueError(f"Error parsing QBO GL CSV: {e}")

    return transactions


# ---------------------------------------------------------------------------
# Format Detection
# ---------------------------------------------------------------------------

def detect_gl_format(filepath: str) -> Optional[str]:
    """
    Auto-detect whether a CSV is FreshBooks GL, QBO GL, or unknown.

    Parameters
    ----------
    filepath : str
        Path to the CSV file

    Returns
    -------
    Optional[str]
        One of: "freshbooks_gl", "qbo_gl", or None if unknown
    """
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(filepath, "r", encoding=encoding) as f:
                raw = f.read(4096)  # Only need the top of the file

            lines = raw.splitlines()
            if not lines:
                return None

            # ── FreshBooks GL: header row contains "Account Number" ──
            first_line = lines[0].lower()
            if "account number" in first_line and "transaction type" in first_line and "debit" in first_line:
                return "freshbooks_gl"

            # ── QBO GL: row 2 says "General Ledger", row 5 has Date/Debit/Credit ──
            if len(lines) >= 2:
                second_line = lines[1].lower() if len(lines) > 1 else ""
                if "general ledger" in second_line:
                    return "qbo_gl"

            # Fallback: check for QBO-style header row at line 5
            if len(lines) > 4:
                row5 = lines[4].lower()
                if "date" in row5 and "transaction type" in row5 and ("debit" in row5 or "credit" in row5):
                    return "qbo_gl"

            return None
        except (UnicodeDecodeError, UnicodeError):
            continue

    return None
